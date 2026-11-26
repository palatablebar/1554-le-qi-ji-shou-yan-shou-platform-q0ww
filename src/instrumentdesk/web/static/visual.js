function renderVisual(target, data) {
    const evidence = data.rows.filter(row => row.hits.length).slice(0,4);
    const slips = evidence.length ? evidence : data.rows.slice(0,2);
    for (const row of slips) {
        const note = node('article',undefined,'evidence-slip');
        const item = node('button',`${row.key} · ${row.zone}`,'item-link');
        item.addEventListener('click',() => inspect(row));
        note.append(item,node('q',row.evidence));
        target.append(note);
    }
}
