# Feature: 技术分析引擎

## User Story
作为一名A股投资者，我希望系统能对个股K线数据进行技术分析（MA、MACD、RSI、成交量），并给出综合多空信号评分，以便我快速判断个股的技术面状态。

## Acceptance Criteria
- [ ] AC-1: 支持计算简单移动平均线（MA），周期包括5/10/20/60/120/250日
- [ ] AC-2: 支持计算指数移动平均线（EMA）
- [ ] AC-3: 支持计算MACD指标（快线、慢线、信号线、柱状图），并识别金叉/死叉
- [ ] AC-4: 支持计算RSI指标，并判断超买/超卖/正常状态
- [ ] AC-5: 支持成交量趋势分析（放量/缩量/正常）
- [ ] AC-6: 支持MA多头排列/空头排列/混乱判断
- [ ] AC-7: 综合各指标输出多空信号评分（-100到100），正值偏多，负值偏空
- [ ] AC-8: 输出中文综合描述文本
- [ ] AC-9: 纯Python实现，不依赖TA-Lib、numpy、pandas等外部计算库
- [ ] AC-10: 输入为KlineBar列表，输出为TechnicalSummary（Pydantic模型）

## Data Flow
Input: list[KlineBar] — 从Layer 2数据获取模块获得的K线数据
Processing:
  1. 从KlineBar列表提取收盘价、成交量序列
  2. 分别计算MA、EMA、MACD、RSI指标
  3. 判断MA排列状态、MACD信号、RSI状态、成交量趋势
  4. 综合各指标计算多空信号评分
  5. 生成中文综合描述
Output: TechnicalSummary — 包含各指标结果、综合评分和描述的Pydantic模型

## API Contract
本模块为纯分析引擎，暂不直接暴露API。供上层业务模块调用：
- 调用入口: `TechnicalAnalyzer.analyze(klines: list[KlineBar]) -> TechnicalSummary`

## Dependencies
- Requires: `src/data/a_share/base.py` (KlineBar模型)
- Provides: TechnicalAnalyzer分析器、TechnicalSummary输出模型，供Layer 4业务模块使用

## Non-functional Requirements
- Performance: 250条K线数据分析耗时不超过100ms
- Security: 无外部网络调用，无安全风险
- Compatibility: 纯Python实现，跨平台兼容

## Skills Evaluation
- Searched: TA-Lib, pandas-ta, tulip-indicators, finta 等技术分析库
- Found: 多个成熟的技术分析库可用
- Decision: ignore — 需求明确要求纯Python实现不依赖外部计算库，且所需指标计算逻辑简单，自行实现即可满足
