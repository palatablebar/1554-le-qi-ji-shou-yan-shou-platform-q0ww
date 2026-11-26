'use strict';
const byId = (id) => document.getElementById(id);
const format = new Intl.NumberFormat('zh-CN', {maximumFractionDigits: 4});
const code = document.body.dataset.endpoint;
const endpoint = `/api/${code}`;
const nav = [...document.querySelectorAll('[data-stage]')];
let currentBatch = null;
const order = {key:'单号',zone:'作业区',estimate:'估计',interval:'估计区间',state:'处置',cost:'用量',reason:'原因码',evidence:'处理依据',drivers:'主要影响项',missing:'缺测量',hits:'命中规则'};
const visibleOrder = ['key','zone','estimate','state','cost'];
let ledger;
let focus = 6;
let currentItem;

function valueOf(item) {
    if (item === null || item === undefined || item === '') return '—';
    if (Array.isArray(item)) return item.map(valueOf).join('、') || '—';
    if (typeof item === 'number') return format.format(item);
    if (typeof item === 'boolean') return item ? '是' : '否';
    return String(item);
}

function node(tag, value, className) {
    const item = document.createElement(tag);
    if (value !== undefined) item.textContent = valueOf(value);
    if (className) item.className = className;
    return item;
}

function appendStatus(message, warning=false) {
    byId('status').textContent = message;
    byId('status').toggleAttribute('data-warning',warning);
}

function rowsTable(records, keys, options={}) {
    const table = node('table');
    const heads = table.createTHead().insertRow();
    for (const key of keys) {
        const heading = node('th',options.labels?.[key] ?? key);
        heading.scope = 'col';
        heads.append(heading);
    }
    const body = table.createTBody();
    for (const value of records) {
        const line = body.insertRow();
        for (const key of keys) {
            const cell = line.insertCell();
            if (key === (options.linkKey ?? 'key') && options.choose) {
                const link = node('button',value[key],'item-link');
                link.type = 'button';
                link.addEventListener('click', () => options.choose(value));
                cell.append(link);
            } else if (key === 'state') {
                const badge = node('span',value[key],'state');
                badge.dataset.state = value[key];
                cell.append(badge);
            } else cell.textContent = valueOf(value[key]);
        }
    }
    return table;
}

function showTables(target, records, options={}) {
    if (!records?.length) {
        target.append(node('p','这一环节暂无记录','empty'));
        return;
    }
    const groups = new Map();
    records.forEach(record => {
        const label = JSON.stringify(Object.keys(record));
        if (!groups.has(label)) groups.set(label,[]);
        groups.get(label).push(record);
    });
    for (const group of groups.values()) target.append(rowsTable(group,Object.keys(group[0]),options));
}

function renderMeasurements(card, row) {
    const labels = ledger.measures;
    const snapshot = node('dl',undefined,'record-fields');
    for (const [key,value] of Object.entries(row.measurements)) {
        snapshot.append(node('dt',labels[key][0]),node('dd',row.unmeasured.includes(key) ? `未报，拟合补值 ${valueOf(value)} ${labels[key][1]}` : `${valueOf(value)} ${labels[key][1]}`));
    }
    card.append(node('h3','单据量测','inner-heading'),snapshot);
    const operations = node('dl',undefined,'record-fields');
    for (const [name,value] of row.operations) operations.append(node('dt',name),node('dd',value));
    card.append(node('h3','作业量计算','inner-heading'),operations);
    if (row.joint_experiments.length) {
        const joint = node('details',undefined,'rejected');
        joint.append(node('summary','联动推演'));
        const entries = row.joint_experiments.map(move => ({情形:move['联动推演'],预测变化:move['变化'],用量:move['用量'],
            作业条件:move['先决条件'],量测:Object.entries(move['联动量测']).map(([name,c])=>`${labels[name][0]} ${c['原值']} → ${c['替换值']}`)}));
        showTables(joint,entries);
        card.append(joint);
    }
    if (row.alternatives.length) {
        card.append(node('h3','单项调整推演','inner-heading'));
        const scenarios = row.alternatives.map(move => ({...move,'变更项':labels[move['变更项']][0],'超训练域':move['超训练域'] ? '需复核' : '—'}));
        showTables(card,scenarios);
    }
}

function showDetail() {
    const card = byId('detail-content');
    card.replaceChildren();
    nav.forEach((button,i) => button.setAttribute('aria-pressed',String(i === focus)));
    if (focus === 'record' && currentItem) {
        byId('detail-title').textContent = '单据详情';
        byId('detail-note').textContent = `${currentItem.key} · ${currentItem.zone}`;
        const details = node('dl',undefined,'record-fields');
        Object.entries(order).forEach(([key,title]) => details.append(node('dt',title),node('dd',currentItem[key])));
        if (currentItem.body_number) {
            details.append(node('dt','琴身编号'),node('dd',currentItem.body_number));
            details.append(node('dt','按琴去向'),node('dd',currentItem['去向'] ?? currentItem.instrument_destination));
        }
        card.append(details);
        if (Array.isArray(currentItem['依据']) && currentItem['依据'].length) {
            const basisBox = node('div',undefined,'instrument-detail-basis');
            basisBox.append(node('h3','按琴判定依据','inner-heading'));
            const list = node('ul',undefined,'basis-list');
            currentItem['依据'].forEach(text => list.append(node('li',text)));
            basisBox.append(list);
            card.append(basisBox);
        }
        const plan = ledger.sections.find(section => section.operating_rows);
        const fieldNotes = plan?.operating_rows.filter(item => item['关联单据'] === currentItem.key);
        if (fieldNotes?.length) {
            card.append(node('h3',plan.operating_title,'inner-heading'));
            showTables(card,fieldNotes);
        }
        renderMeasurements(card,currentItem);
        return;
    }
    const panel = ledger.sections[focus];
    byId('detail-title').textContent = panel.title;
    byId('detail-note').textContent = panel.summary;
    if (panel.operating_rows?.length) {
        const plan = node('details',undefined,'rejected');
        plan.append(node('summary',`${panel.operating_title} · ${panel.operating_rows.length} 条`));
        showTables(plan,panel.operating_rows,{linkKey:'关联单据',choose: record => {
            const ticket = ledger.rows.find(item => item.key === record['关联单据']);
            if (ticket) inspect(ticket);
        }});
        card.append(plan);
    }
    showTables(card,panel.records);
    if (panel.errors.length > 0) {
        const rejected = node('details',undefined,'rejected');
        rejected.append(node('summary',`隔离 ${panel.errors.length} 条`));
        showTables(rejected,panel.errors);
        card.append(rejected);
    }
}

function inspect(ticket) {
    focus = 'record';
    currentItem = ticket;
    showDetail();
    byId('detail-title').focus({preventScroll:true});
    byId('detail').scrollIntoView({block:'nearest'});
}

function showQueue() {
    if (!ledger) return;
    const sought = byId('filter').value.trim().toLocaleLowerCase('zh-CN');
    const state = byId('status-filter').value;
    const rows = ledger.rows.filter(item => (!state || item.state === state) &&
          (!sought || [item.key,item.body_number,item['琴身编号'],item.zone,item.reason,item.evidence,
                       item['去向'],Array.isArray(item['依据']) ? item['依据'].join(' ') : '']
              .filter(text => text !== null && text !== undefined)
              .some(text => String(text).toLocaleLowerCase('zh-CN').includes(sought))));
    byId('row-count').textContent = `${rows.length}/${ledger.rows.length} 条`;
    byId('work-rows').replaceChildren(rows.length ? rowsTable(rows,visibleOrder,{labels:order,choose:inspect}) : node('p','当前条件下没有匹配单据','empty'));
}

function instrumentCards() {
    return ledger?.instruments ?? [];
}

function renderInstrumentLookup() {
    const target = byId('instrument-result');
    if (!target || !ledger) return;
    const input = byId('instrument-filter');
    const sought = (input?.value ?? '').trim().toLocaleLowerCase('zh-CN');
    target.replaceChildren();
    if (!sought) return;
    const matches = instrumentCards().filter(card =>
        String(card.body_number ?? '').toLocaleLowerCase('zh-CN').includes(sought));
    if (!matches.length) {
        target.append(node('p', `没有琴身编号匹配“${input.value.trim()}”；无编号琴请用下方查单按原单号查询。`, 'empty'));
        return;
    }
    for (const card of matches) {
        const box = node('div', undefined, 'instrument-card');
        const head = node('div', undefined, 'instrument-card-head');
        head.append(node('strong', `琴 ${card.body_number}`));
        const badge = node('span', card['去向'] || card.destination, 'state');
        badge.dataset.state = card.state;
        head.append(badge);
        box.append(head);
        const grid = node('dl', undefined, 'record-fields');
        const add = (dt, dd) => grid.append(node('dt', dt), node('dd', dd));
        add('去向', card['去向']);
        add('签发单号', card.signed_key ?? '暂不签发');
        add('接单最新挂牌', card.accepted_key ?? '—');
        if (card.cohort) add('实测门店', card.cohort);
        if (card.actual_photos !== undefined) add('新单实拍照片', `${card.actual_photos ?? '未实测'} 张（满 7 张解除补照）`);
        add('涉及单据', (card.all_keys ?? card.listing_keys ?? []).join('、') || '—');
        box.append(grid);
        const basis = node('ul', undefined, 'basis-list');
        for (const reason of (card['依据'] ?? card.basis ?? [])) basis.append(node('li', reason));
        box.append(node('h4', '判定依据', 'inner-heading'), basis);
        const keys = card.all_keys ?? card.listing_keys ?? [];
        const openKey = card.signed_key || card.accepted_key || keys[0];
        const ticket = ledger.rows.find(item => item.key === openKey);
        if (ticket) {
            const button = node('button', '查看单据处置与量测', 'ghost');
            button.type = 'button';
            button.addEventListener('click', () => inspect(ticket));
            box.append(button);
        }
        target.append(box);
    }
}

function syncInstrumentFromFilter() {
    // 查单框输入琴身编号时，同步展开“按琴查询”的去向依据卡。
    const q = byId('filter')?.value.trim() ?? '';
    const box = byId('instrument-filter');
    if (box && q && instrumentCards().some(c => String(c.body_number).includes(q))) {
        box.value = q;
    }
    renderInstrumentLookup();
}

function redraw(data) {
    ledger = data;
    if (focus === 'record') focus = 6;
    byId('stamp').textContent = data.run_id;
    byId('capacity').value = data.capacity;
    byId('mode').value = data.mode;
    byId('kpis').replaceChildren(...data.metrics.map(item => {
        const result = node('div',undefined,'kpi');
        result.append(node('dt',item.label),node('dd',item.value));
        return result;
    }));
    const plot = byId('plot');
    plot.replaceChildren();
    renderVisual(plot,data);
    showQueue();
    renderInstrumentLookup();
    showDetail();
    byId('save').disabled = false;
}

async function requestResult(path, options) {
    const response = await fetch(endpoint+path,options);
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || '读取失败');
    return result;
}

async function prepare() {
    try {
        redraw(await requestResult('/overview'));
        byId('apply').disabled = false;
        appendStatus('本班已载入');
    } catch (error) {
        appendStatus(error.message,true);
        byId('retry').hidden = false;
    }
}

nav.forEach((control,i) => control.addEventListener('click',() => {
    if (!ledger) return;
    focus = i;
    showDetail();
    byId('detail').scrollIntoView({block:'nearest'});
    byId('detail-title').focus({preventScroll:true});
}));
byId('filter').addEventListener('input',() => { showQueue(); syncInstrumentFromFilter(); });
byId('instrument-filter').addEventListener('input',renderInstrumentLookup);
byId('status-filter').addEventListener('change',showQueue);
byId('scenario').addEventListener('submit',async (event) => {
    event.preventDefault();
    const submit = byId('apply');
    submit.disabled = true;
    appendStatus('正在复算');
    try {
        const data = {capacity:byId('capacity').valueAsNumber,strategy:byId('mode').value};
        const result = await requestResult('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...currentBatch,...data})});
        redraw(result);
        appendStatus('处置方案已更新');
    } catch (error) {
        appendStatus(error.message,true);
    } finally {
        submit.disabled = false;
    }
});
byId('save').addEventListener('click',() => {
    if (!ledger) return;
    const content = new Blob([JSON.stringify(ledger,null,2)],{type:'application/json'});
    const url = URL.createObjectURL(content);
    const download = node('a');
    download.href = url;
    download.download = `${code}-${ledger.run_id}.json`;
    document.body.append(download);
    download.click();
    download.remove();
    setTimeout(() => URL.revokeObjectURL(url),1000);
});
byId('print')?.addEventListener('click',() => window.print());
byId('retry').addEventListener('click',() => {byId('retry').hidden = true;prepare();});
byId('batch-file').addEventListener('change',async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const submit = byId('apply');
    submit.disabled = true;
    try {
        if (file.size > 1450000) throw new Error('请导入小于 1.45 MB 的单据文件');
        const incoming = JSON.parse(await file.text());
        if (!incoming || !Array.isArray(incoming.records)) throw new Error('文件须包含 records 数组');
        const custom = {records:incoming.records,as_of:incoming.as_of ?? 96};
        const setting = {capacity:ledger?.capacity ?? 12,strategy:ledger?.mode ?? 'balanced'};
        const data = await requestResult('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...custom,...setting})});
        currentBatch = custom;
        byId('source-label').textContent = file.name;
        byId('restore').hidden = false;
        redraw(data);
        appendStatus('已载入自备批次');
    } catch (error) {
        appendStatus(error.message,true);
    } finally {
        event.target.value = '';
        submit.disabled = !ledger;
    }
});
byId('restore').addEventListener('click',async () => {
    const reset = byId('restore');
    reset.disabled = true;
    try {
        const refreshed = await requestResult('/overview');
        currentBatch = null;
        byId('source-label').textContent = '随附样例';
        reset.hidden = true;
        redraw(refreshed);
        appendStatus('已恢复样例');
    } catch (error) {
        appendStatus(error.message,true);
    } finally {
        reset.disabled = false;
    }
});
(() => {
    const params = new URLSearchParams(location.search);
    const q = params.get('body') || params.get('body_number') || params.get('instrument')
              || params.get('qin') || params.get('q');
    const box = byId('instrument-filter');
    if (q && box) box.value = q;
})();
prepare();