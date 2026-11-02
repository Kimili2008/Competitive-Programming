# 大尺寸 Masyu 压力测试

在项目目录 `/Users/kimi/KimiWork/Competitive-Programming/QRT` 中运行。

## 生成并运行所有测试

```bash
python3 stress4.py
```

默认逐题打印完整 input、实际 output、错误信息和已知合法解。
仅在终端显示进度、将完整内容保存到文件：

```bash
python3 stress4.py --quiet
```

单题硬性上限为 10 秒，顺序运行以减少计时相互干扰。当前求解器内部搜索预算为 9 秒。
每次运行会新建 `seed_20261027/run_001`、`run_002` 等目录，保留之前的结果。

## 查看每题输入和输出

- `cases/名字.in`：题目输入，第一行为行数。
- `run_001/名字.out`：求解器实际 stdout，失败时可能为空。
- `run_001/名字.stderr.txt`：求解器错误信息。
- `run_001/名字.witness.out`：构造题目时保存的合法解，不是求解器输出。
- `run_001/all_inputs_outputs.md`：每题完整 input、实际 output、错误和合法解，汇总在一个文件中。
- `run_001/summary.md`：逐题状态、时间、长度和珍珠数。
- `run_001/results.csv`、`results.json`：便于比较不同版本的结构化结果。
- `run_001/solver_snapshot.py`、`run.json`：当次求解器源码、校验值和运行环境。

## 重跑某题或生成另一批题

```bash
python3 stress4.py --case random_01_sparse
python3 stress4.py --seed 20261028 --quiet
python3 stress4.py --generate-only
```

生成器先构造一条简单闭环，再只在满足规则的位置放珍珠。
24 题覆盖随机路线、狭窄通道、蛇形路线，以及四种珍珠密度；另有 2 道大尺寸基准题。
大多数题为 50×50，其余为 48×50 或 50×40。固定种子可重现题目。
珍珠更多并不必然更难：约束更强也可能让搜索更快。实际难度由求解器的运行结果衡量。

除两个基准题外，已知合法解的长度未证明最优。
`witness_relative_score` 用该合法解长度代入评分公式，属于偏乐观的本地比较指标，不能当成官方分数。
某题的求解器输出为空，仍会保留原样，不会用已知合法解替换。
`no_solution` 表示程序没有找到答案，不表示题目无解；这些题目均保存了通过验证的合法解。
`timeout` 表示超出外部 10 秒上限，`error` 表示程序出现其他异常，`invalid` 表示输出违反规则。

## 快速检查测试工具

```bash
python3 -m unittest -v test4.py test_stress4.py test_optimized4.py
```

该命令检查求解器的基本行为、生成题目的合法性和种子可重现性，不会执行整批耗时压力测试。

## 当前合并版本

主程序统一为 `p4.py`；`p4_candidate.py` 仅保留兼容入口。
求解器、合法性检查 `validate_masyu`、评分函数 `score_masyu` 均位于主程序中。

```bash
python3 p4.py < sample4.txt > output.txt
python3 benchmark4.py sample4.txt --reference-length 18
```

本轮优化预计算每个候选集合是否已确定连接方向，仅在该方向发生变化时更新相邻格的搜索优先级。
保留原有候选削减、回滚和合法性检查，搜索预算仍为 9 秒。
三个案例在独立的一秒搜索预算下，节点处理量分别提高约 19%、16%、21%。
这是本机单次测量，受负载影响；节点处理量提升不代表通过率同幅提升。
完整结果及每题真实输入、输出见本轮运行目录 `seed_20261027/run_004`。
