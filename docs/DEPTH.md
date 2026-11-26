# 乐器寄售验收台验证目录

AI/ML · 传统ML · 中型

修改业务链路时先检查受影响模块的测试，再运行整套 `pytest`。回归记录须能够定位到具体单据或计算值。

## 功能模块

| 编号 | 功能 | 核对内容 | 核心文件 | 独立测试 |
|---|---|---|---|---|
| M1 | 寄售登记 | 单据版次与隔离 | `src/instrumentdesk/consignment_notes/service.py` | `tests/test_consignment_notes.py` |
| M2 | 退货观察 | 截止日和成熟标签 | `src/instrumentdesk/return_observation/service.py` | `tests/test_return_observation.py` |
| M3 | 验收证据 | 原始数据到特征 | `src/instrumentdesk/instrument_evidence/service.py` | `tests/test_instrument_evidence.py` |
| M4 | 退货先验 | 训练及可重复推断 | `src/instrumentdesk/return_prior_claim/service.py` | `tests/test_return_prior_claim.py` |
| M5 | 寄售回放 | 回放误差及可信区间 | `src/instrumentdesk/consignment_eval/service.py` | `tests/test_consignment_eval.py` |
| M6 | 门店分组 | 差异定位和外推审查 | `src/instrumentdesk/shop_mix/service.py` | `tests/test_shop_mix.py` |
| M7 | 二次验收 | 硬规则与额度分配 | `src/instrumentdesk/authentication_window/service.py` | `tests/test_authentication_window.py` |
| M8 | 品相签记 | 单据及额度证据 | `src/instrumentdesk/condition_note/service.py` | `tests/test_condition_note.py` |
| M9 | 跨店重挂琴身登记 | 最新挂牌、补照解除、一琴一单与泄漏隔离 | `src/instrumentdesk/instrument_registry/service.py` | `tests/test_cross_shop_relisting.py` |

## 深度登记

| 编号 | 边界 | 判断 | 处理位置 | 测试定位 |
|---|---|---|---|---|
| TRAP-14 | 同版不同读数 | 两条都隔离，换序结论一致 | `src/instrumentdesk/consignment_notes/service.py` | `tests/test_consignment_notes.py::test_conflicting_same_version_is_order_independent` |
| TRAP-19 | 多个规则或外推标记重叠 | 硬约束优先，保留全部命中码 | `src/instrumentdesk/authentication_window/service.py` | `tests/test_authentication_window.py::test_hard_rule_precedes_outside_reference` |
| TRAP-23 | 标签落在窗口的终点 | 终点进入隔离段，窗口为半开区间 | `src/instrumentdesk/return_observation/service.py` | `tests/test_return_observation.py::test_half_open_days` |
| TRAP-32 | 大偏移细方差与常数列 | 中心化后累加，常数列尺度为一 | `src/instrumentdesk/instrument_evidence/service.py` | `tests/test_instrument_evidence.py::test_cancellation_safe_scaling` |
| TRAP-42 | 拟合窗口后才回传结果 | 依标签成熟时间屏蔽，未来数据不参与拟合 | `src/instrumentdesk/return_observation/service.py` | `tests/test_return_observation.py::test_mature_label_cannot_cross_partition` |
| TRAP-43 | 回放没有成熟记录 | 记录未定义状态，避免以零误差替代 | `src/instrumentdesk/consignment_eval/service.py` | `tests/test_consignment_eval.py::test_no_outcome_gets_undefined_metrics` |
| TRAP-44 | 校准样本不足 | 分派前转人工判读并保留原因 | `src/instrumentdesk/consignment_eval/service.py` | `tests/test_consignment_eval.py::test_empty_calibration_requires_review` |
| TRAP-53 | 单条推断与混批 | 复用冻结参数，各条估计完全一致 | `src/instrumentdesk/return_prior_claim/service.py` | `tests/test_return_prior_claim.py::test_input_batch_invariance` |
| TRAP-54 | 特征版本与模型不配对 | 拒绝继续推断并要求重拟合 | `src/instrumentdesk/return_prior_claim/service.py` | `tests/test_return_prior_claim.py::test_mismatched_model_input_version_fails` |
| TRAP-61 | 同日最新挂牌读数冲突 | 两张都转人工，换序结论一致 | `src/instrumentdesk/instrument_registry/service.py` | `tests/test_cross_shop_relisting.py::test_same_day_conflicting_latest_goes_manual` |
| TRAP-62 | 旧补照暂停被新挂牌绕过 | 新单实拍未满七张继续暂停，满七张才解除 | `src/instrumentdesk/instrument_registry/service.py` | `tests/test_cross_shop_relisting.py::test_photo_hold_only_releases_at_seven_actual_photos` |
| TRAP-63 | 同琴多单重复签发 | 一个琴身编号至多一张已分派，换序不变 | `src/instrumentdesk/authentication_window/service.py` | `tests/test_cross_shop_relisting.py::test_one_signing_per_body_and_reorder_invariant` |
| TRAP-64 | 训练琴回流校准/回放 | 命中训练琴身即退出两窗并登记泄漏 | `src/instrumentdesk/return_observation/service.py` | `tests/test_cross_shop_relisting.py::test_training_seen_body_leaves_calibration_and_replay` |
