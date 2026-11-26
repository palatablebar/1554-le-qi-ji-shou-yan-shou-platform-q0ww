# 乐器寄售验收台

二手琴行验收专员用这套工作台处理乐器寄售退货风险与二次验收。进入工作台可调整本班复核额度，查看每张寄售单的预测、命中规则和处置，导出单班可复算记录。

## 本地运行

```sh
docker compose up -d --build
```

访问 `http://127.0.0.1:18653`。样例是可复算的模拟班次，涵盖正常历史、较迟回执、最新冲突版、缺测单和临时分区。

```sh
docker compose exec -T app python -m instrumentdesk.entry evaluate --capacity 8 --strategy focus
docker compose exec -T app pytest -q
docker compose down --remove-orphans
```

## 跨店重挂与按琴查询

同一琴身编号（`body_number`，兼容 `serial_number`、`琴身编号` 等写法）的跨店重挂单只签发一张二验：截止前到站的最新挂牌用新店实测预测风险并接单，同日最新挂牌读数冲突转人工；旧单的 `MISSING_DETAIL` 补照暂停延续到新单实测照片满七张才解除。训练拟合见过的琴身退出校准与回放以防样本泄漏；无琴身编号的单据沿用原单。裁决与输入顺序无关。

页面顶部“按琴查询”输入琴身编号即可看到去向和判定依据，也可访问 `/?body=<编号>` 或 `GET /api/instrumentdesk/instruments/<编号>`。

[字段和时间窗](docs/SPEC.md) · [模块与回归表](docs/DEPTH.md) · [HTTP 与自备数据](docs/RUNBOOK.md)
