"""宏观指标定义：预定义追踪的宏观经济指标列表。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorDef:
    """单个宏观指标的定义。"""

    name: str
    """指标中文名称。"""

    category: str
    """分类：价格、货币、利率、市场、国际、商品。"""

    akshare_api: str
    """AkShare API 函数名。"""

    frequency: str
    """更新频率：daily / monthly / event。"""

    unit: str
    """数据单位。"""

    value_column: str
    """从 AkShare 返回 DataFrame 中提取值的列名。"""

    description: str = ""
    """指标描述。"""


# -- 预定义宏观指标列表 --

MACRO_INDICATORS: list[IndicatorDef] = [
    # ---- 价格类（月度） ----
    IndicatorDef(
        name="CPI",
        category="价格",
        akshare_api="macro_china_cpi_monthly",
        frequency="monthly",
        unit="%",
        value_column="同比增长",
        description="居民消费价格指数同比",
    ),
    IndicatorDef(
        name="PPI",
        category="价格",
        akshare_api="macro_china_ppi_monthly",
        frequency="monthly",
        unit="%",
        value_column="同比增长",
        description="工业生产者出厂价格指数同比",
    ),
    # ---- 货币类（月度） ----
    IndicatorDef(
        name="M1",
        category="货币",
        akshare_api="macro_china_money_supply",
        frequency="monthly",
        unit="亿元",
        value_column="M1-数量",
        description="狭义货币供应量",
    ),
    IndicatorDef(
        name="M2",
        category="货币",
        akshare_api="macro_china_money_supply",
        frequency="monthly",
        unit="亿元",
        value_column="M2-数量",
        description="广义货币供应量",
    ),
    # ---- 利率类（日/月度） ----
    IndicatorDef(
        name="LPR-1Y",
        category="利率",
        akshare_api="macro_china_lpr",
        frequency="monthly",
        unit="%",
        value_column="LPR1Y",
        description="1年期贷款市场报价利率",
    ),
    IndicatorDef(
        name="LPR-5Y",
        category="利率",
        akshare_api="macro_china_lpr",
        frequency="monthly",
        unit="%",
        value_column="LPR5Y",
        description="5年期以上贷款市场报价利率",
    ),
    IndicatorDef(
        name="Shibor-ON",
        category="利率",
        akshare_api="rate_interbank",
        frequency="daily",
        unit="%",
        value_column="Shibor人民币-隔夜",
        description="上海银行间同业拆放利率（隔夜）",
    ),
    IndicatorDef(
        name="国债收益率-10Y",
        category="利率",
        akshare_api="bond_zh_us_rate",
        frequency="daily",
        unit="%",
        value_column="中国国债收益率10年",
        description="中国10年期国债收益率",
    ),
    IndicatorDef(
        name="国债收益率-1Y",
        category="利率",
        akshare_api="bond_zh_us_rate",
        frequency="daily",
        unit="%",
        value_column="中国国债收益率2年",
        description="中国2年期国债收益率（近似1Y）",
    ),
    # ---- 市场类（日度） ----
    IndicatorDef(
        name="融资余额",
        category="市场",
        akshare_api="stock_margin_sz_sh_total",
        frequency="daily",
        unit="亿元",
        value_column="融资余额",
        description="沪深两市融资余额",
    ),
    IndicatorDef(
        name="北向资金净流入",
        category="市场",
        akshare_api="stock_hsgt_north_net_flow_in_em",
        frequency="daily",
        unit="亿元",
        value_column="净流入",
        description="北向资金（沪股通+深股通）当日净流入",
    ),
    # ---- 商品类（日度） ----
    IndicatorDef(
        name="WTI原油",
        category="商品",
        akshare_api="futures_foreign_commodity_realtime",
        frequency="daily",
        unit="美元/桶",
        value_column="最新价",
        description="WTI 原油期货价格",
    ),
    IndicatorDef(
        name="COMEX黄金",
        category="商品",
        akshare_api="futures_foreign_commodity_realtime",
        frequency="daily",
        unit="美元/盎司",
        value_column="最新价",
        description="COMEX 黄金期货价格",
    ),
]


def get_indicators_by_category(category: str) -> list[IndicatorDef]:
    """按类别获取指标列表。"""
    return [ind for ind in MACRO_INDICATORS if ind.category == category]


def get_indicator_by_name(name: str) -> IndicatorDef | None:
    """按名称获取指标定义。"""
    for ind in MACRO_INDICATORS:
        if ind.name == name:
            return ind
    return None
