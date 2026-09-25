# 程序与结果说明

本目录为论文配套材料。当前数值版本为v004，问题三为25个运输任务、6个中继任务及5个悬停点；当前结果与论文一致。

## 文件

- tables/official_results.xlsx：官方六类结果表，以及补充的问题三运输架次和逐箱交付表。
- tables/q3_supplement.xlsx：问题三完整运输、资源、通信区间与边界，以及问题四两种口径的分区。
- checking_notes.md：检查范围、判据和关键结果。
- results/：六份当前结果JSON，包括问题一两目标、问题二、问题三、问题四主口径与禁止复制对照。
- src/、config/：计算、固定决策回算和独立检查程序及所需配置。
- data/original/：实际运行所需的五份基础Excel与一份DEM TIFF，保持题目相对目录；表格仅清理文档属性，单元格数据未变。
- figures/：论文28幅图的PNG、SVG、代码和同名CSV；data/下8份CSV为共享绘图输入。
- paper_tables/：从当前论文22张编号表逐值提取的CSV与工作簿，不含历史过程表。

## 环境与运行

使用Python 3.11，依赖版本列于requirements.txt。科学图需要本机有宋体及Times New Roman字体。

请先复制本目录到独立运行位置。在复制目录内执行：

```text
python run_checks.py
```

此命令把当前结果复制至新建的output/reproduced，重算物理约束、全部连续通信区间与瞬时、实际状态、并发和加强下界，并独立枚举核对问题四；不搜索运输计划、不改results。结果写在output/reproduced/checks。重复运行请换用新副本，避免覆盖先前输出。

按既定决策从原始输入重算问题二、三，可另在独立副本执行：

```text
python src/replay_fixed_results.py --decisions config/q2_fixed_decisions.json --output output/replay_q2.json
python src/replay_fixed_results.py --decisions config/q3_fixed_decisions.json --output output/replay_q3.json
python src/compare_fixed_results.py --reference results/q2.json --replayed output/replay_q2.json --output output/q2_comparison.json
python src/compare_fixed_results.py --reference results/q3.json --replayed output/replay_q3.json --output output/q3_comparison.json
```

两条回算命令保留箱、路线、时序和资源决策，重新计算物理量与连续通信证明，不表示再次搜索能得到同一最优方案。输出目录不存在时程序会创建；不得把回算输出覆盖回results。

src/solve_q1.py可从原始输入重新计算问题一两种目标顺序。完成run_checks.py后，src/solve_q4.py可对已经核验的固定问题三重新枚举两种中继口径；结果仅写运行副本的output。

在本目录执行“python 重新绘制全部图片.py”可重绘28图。绘图只读当前数据，输出PNG/SVG与辅助CSV/相对路径元数据，不生成论文文档。部分通信模块保留兼容模块名，输入统一为本目录当前结果，不加载历史解答。

## 数值说明

H1为明确采用的模型解释，连续判定使用0.01 dB与1 m数值门槛，不据此声称现实无线可靠度。问题二、三为可行方案，问题四最优性限于固定任务、时刻、完整保障关系、给定口径和目标顺序。

结果中保留的旧标称精度字段为80；实际生成与回算使用100位工作上下文。固定任务时钟从原始物理回算发现12处双精度末位差异，最大约1.82e-12 s；先核时钟差，再依既定时序完整重建连续证书，不放宽通信预算、不删除瞬时。

本目录不含历史问题二能耗对照及历史过程表。运行生成的output是复核工作记录，不属于本次文件清单；文件清单只针对交付时的静态材料。
