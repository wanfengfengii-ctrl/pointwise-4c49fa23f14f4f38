# 耐压试验室工艺交班台账

日班依据台架作业规程登记工艺，班组提交带出处的实际动作。质控员在停源后比较两份冻结修订，根据独有记录安排复查。次班用报告号核对当时所用的实收件和首执。

## 运行

需要 Python 3.11 和标准库。所有命令从项目根目录运行。

```sh
python3 -B check_project.py
python3 -B -m unittest discover -s tests -t .
python3 -B -m reports.workbench demo
```

第一条是控制台提供的完整核验入口。第二条直接运行同一原套件。演示读取 `samples/workday.json`，在独立临时目录登记旧版、核对班单、登记勘误、冻结两版、关闭源库、收件签报并重开领取。旧版独有记录为 `['补', '检']`，新版独有记录为 `['复', '检']`。演示还登记 `samples/reconciliation.json` 首例并办理双源核对，输出签存结论，再重开源库按号领取。演示输出实际核对结论、实收父件、签报和次班领取结果。

## 工作台

`python3 -B -m reports.workbench --workspace .workbench init` 建立 `source.sqlite3` 和 `center.sqlite3`，可重复运行。后续命令使用相同的 `--workspace`，缺省为 `.workbench`。

| 子命令 | 交接结果 |
| --- | --- |
| `register SPEC.json` | 登记修订，返回修订号。输入文件为样例中 `old` 或 `new` 对象的形状 |
| `check REVISION CREW [ACTION ...]` | 核对并归档原序动作和班组出处 |
| `trace TRACE_ID` | 读取入档记录及当时的结论 |
| `freeze REVISION OUT.json` | 发行指定修订并导出固定字节 |
| `issue ISSUE_ID OUT.json` | 按发行号重新导出原件 |
| `receive ISSUE_ID IN.json` | 验收固定件并返回实收号 |
| `compare LEFT_ID RIGHT_ID` | 以请求顺序签存双向差异和首执 |
| `report REPORT_ID` | 领取旧报告，未知号输出 `null` |

文件导出使用新路径。原件一经发行即可按号重新导出。非法输入、缺件、存储或提交错误由工作台以非零退出码报告。

## Python 接口

用 `reports.workbench.initialize_workspace(directory)` 初始化两个库。用 `reports.workbench.open_database(path)` 打开既有库，该上下文会启用外键并在退出时关闭连接。直接传入 SQLite 连接时，也应开启外键检查。写入入口在空闲连接上管理各自的事务。编号为台账内的正整数。这个工作台配置一间实验室的单个源库和单个中心库。

| 模块与入口 | 输入与返回 |
| --- | --- |
| `recipes.register.register(db, recipe, codes, steps, start, accepting, edges)` | 源库、工艺标识、动作目录、步骤集合、起点、完结点、转移。返回修订号 |
| `recipes.repository.get_revision(db, revision_id)` | 返回指定修订的不可变快照 |
| `recipes.repository.get_current_revision(db, recipe)` | 返回工艺的当前修订快照 |
| `records.intake.check_record(db, revision_id, actions, crew)` | 返回包含 `trace_id`、`revision_id`、`actions`、`crew`、`supported` 的 `TrialTrace` |
| `records.traceback.get_trace(db, trace_id)` | 返回原入档记录 |
| `records.intake.reconcile_trial(db, trial_key, revision_id, controller, crew)` | 双源核对并签存，返回含 `reconciliation_id`、`trial_key`、`revision_id`、`controller`、`crew`、`actions`、`positions`、`confirmed` 的普通字典 |
| `records.traceback.get_reconciliation(db, reconciliation_id)` | 按号领取双源核对签存；未知号抛 `LookupError`，非法编号抛 `ValueError` |
| `issue.freeze.freeze(db, revision_id)` | 返回 `FrozenEvidence`，含 `issue_id`、`revision_id`、`digest`、公开判定和固定 `wire` 字节 |
| `issue.archive.get_issue(db, issue_id)` | 按号返回原件 |
| `compare.admission.receive(db, issue_id, wire)` | 验收并返回中心实收号 |
| `compare.pairing.compare_pair(db, left_id, right_id)` | 返回 `SignedReport`，含报告号、双向见证、按序父件和首执 |
| `reports.lookup.get_report(db, report_id)` | 返回签存快照或 `None` |
| `reports.export.export_report(report)` | 将签存快照编码为 JSON |

动作码、工艺标识、内部编号和班组出处是非空白的精确文本。转移输入是对象，必须有 `source`、`target`、`code`，可有 `note`。`code` 为 `null` 表示隐藏边。两端步骤必须声明，公开动作必须在本修订目录中。更正追加新修订并原子推进当前指针。错误输入抛出 `ValueError`，源端和实收台账的缺号查询抛出 `LookupError`。合法输入即使无法完结，班单也会留存。

## 判定与交接

一个记录是动作码的有序序列。只要存在从起点到合法完结点的一条路径，删去隐藏步骤后正好得到该记录，该修订就支持它。同一动作码可以出现在多条出边上。动作可以重复，隐藏步骤也可形成循环。起点能直接或经隐藏步骤完结时支持空记录。`补检` 在样例中是两个动作。

V1 固定件为 UTF-8 JSON，使用按键排序、无额外空白的紧凑编码，非 ASCII 字符使用 JSON 转义。外层为 `version`、`issue_id`、`revision_id`、`body` 和 `digest`。摘要是其余四个字段按同一规则编码后的 SHA-256 小写十六进制值，用于检验身份与传输字节的一致性。正文包含 `codes`、`state_count`、`start`、`accepting` 和 `transitions`。状态编号在 `0` 到 `state_count - 1` 内。每条边为 `[起状态, 公开动作码, 终状态]`。同一状态和动作可有多个目标。内部原始编号、备注、班组及实际试验记录留在源库。同字节重送取得原实收号，同发行号的冲突件拒收。

中心用两件各自的续接与完结资格判断同一完整记录，按动作数返回每方向最短见证。同长时逐项按 Unicode 码点序比较动作码。可继续但未完结的路径不会贡献支持。循环通过可达的联合候选状态判断，JSON `[]` 表示空记录见证，`null` 表示该方向无独有记录。中心一次提交差异、两份有序父件快照和本报告首执。缺件、非法请求及提交失败不会新增报告或回执。更正和重新初始化不会重算旧报告。

## 双源漏记核对

`reconcile_trial` 把控制器片段与班组原页嵌入同一条修订路径的公开动作序列。每单绑定试验标识、确切修订号、双方精确出处和原序动作；动作码沿用本修订目录校验，原据 `actions` 统一以列表返回。合法还原是从起点到完结点的一条完整路径，隐藏边不产生公开动作也不占位；两份原据各自按原序成为还原的子序列，同源位置严格递增，异源原位可共用同一公开动作，还原也可含双方都漏记的动作。

按公开动作个数取最短，签存一条最短还原及一份代表性合法对照（`positions` 的两份还原位置列表，与原据原位都从 1 起算）。确认同拍覆盖所有最短还原及其全部合法对照：只要存在一份等长完结或对照让两笔落在不同位置，该双源原位对就不签为确认；`confirmed` 按 `[控制器原位, 班组原位]` 升序。可空完结返回 `actions=[]`、空位置和空确认；无共同完结仍留存双方原据，`actions` 与 `positions` 为 `None`、`confirmed` 为空。提交失败不新增且解除后可重试，工艺更正及重新初始化后按原号领取原签存。样例与期望见 `samples/reconciliation.json`。

## 原回归

`tests/test_recipes.py` 和 `tests/test_records.py` 核对勘误拒绝、指定旧修订、原序及出处。`tests/test_handoff.py` 核对原件、隐私、完结语义、损坏传输和重送。`tests/test_comparison.py` 核对停源双向结果、交换父件、同长择一、晚出现的差异、等价循环和空见证。`tests/test_reporting.py` 使用 SQLite 延迟外键约束核对提交失败的实际回滚和重试，并验证历史首执。`tests/test_workday.py` 和 `tests/test_initialization.py` 核对全日剧本、重开领取和已有业务数据上的重复初始化。`tests/test_reconciliation.py` 核对双源最短还原、代表性原位对照、确认同拍的全域判定、无共同完结留档、空动作完结、非法输入、失败回滚重试以及重开按号领取。
