# 量化研究数据来源指南

## 核心数据库

### 国泰安 CSMAR（首选）
- **网址**：csmar.com（需机构账号）
- **特点**：A股最全面的学术数据库，高校普遍有订阅
- **主要数据表**：

| 数据类型 | 数据表 | 关键字段 |
|---------|-------|---------|
| 月度股票收益+市值 | TRD_Mnth | Mretwd（月收益率）、Msmvttl（总市值） |
| 无风险收益率 | TRD_Nrrate | Nrr1='NRI01'（1年期国债），Nrrmtdt（月度收益%） |
| 股票基本信息 | TRD_Co | Stkcd、Markettype（市场类型）、Nnindcd（行业代码） |
| 财务数据（PB等） | FI_T10 | F100401A（PB ratio） |
| FF3因子 | STK_MKT_THRFACMONTH | RiskPremium1、SMB1、HML1 |
| FF5因子 | STK_MKT_FIVEFACMONTH | RiskPremium1、SMB1、HML1、RMW1、CMA1 |
| 日度收益率 | TRD_Dalyr | Dretwd |

**重要字段说明**：
- `Markettype`：1=上交所A股，4=深交所A股，16=创业板，32=科创板，64=北交所
- 通常筛选 Markettype ∈ {1, 4, 16}（沪深A+创业板），排除科创板和北交所
- `ST`股：通过股票名称包含"ST"来识别并剔除
- 金融股：行业代码以"J"开头（证券、银行、保险），通常剔除

### Wind 金融终端
- **特点**：数据更新及时，部分高频数据更全，但价格昂贵
- **学生获取**：通过学校Bloomberg/Wind终端，或Wind量化研究版（WindPy）
- 适用于：实时数据、债券、衍生品、宏观数据

### Tushare Pro（免费替代方案）
- **网址**：tushare.pro（需注册获取token）
- **特点**：免费，API获取，数据较全但有些许延迟
- 适用于：基础行情数据、财务数据、新闻数据
```python
import tushare as ts
ts.set_token('your_token')
pro = ts.pro_api()
df = pro.monthly(ts_code='000001.SZ', start_date='20130101', end_date='20231231')
```

---

## 各类数据的标准获取方式

### 股票月度收益率
**CSMAR方法（推荐）**：
```python
# TRD_Mnth.xlsx
# 字段：Stkcd（6位股票代码）, Trdmnt（年月，格式'2013-01'）
#       Mretwd（月度收益率，已考虑分红复权）, Msmvttl（总市值，万元）
df = pd.read_excel('TRD_Mnth.xlsx')
df['date'] = pd.to_datetime(df['Trdmnt'])
```

### 无风险收益率
**CSMAR TRD_Nrrate**：
```python
rf_df = pd.read_excel('TRD_Nrrate.xlsx')
# Nrr1='NRI01' 为1年期国债
rf_month = rf_df[rf_df['Nrr1']=='NRI01'].copy()
rf_month['Rf'] = rf_month['Nrrmtdt'] / 100 / 12  # 年化% → 月度小数
```

### 账面市值比（B/M）
```python
# FI_T10.xlsx 中 F100401A = PB ratio
# BM = 1/PB
# 注意：财报发布有滞后，需要将财报数据与使用时间对齐
# 一季报（Q1）：约4月30日发布 → 可在5月使用
# 半年报（Q2）：约8月31日发布 → 可在9月使用
# 三季报（Q3）：约10月31日发布 → 可在11月使用
# 年报（Q4）：次年4月30日发布 → 可在次年5月使用
```

### 动量因子
```python
# 动量 = 过去12个月-跳过最近1个月的累计收益
# 即 t-12 到 t-2 的累计对数收益
def calc_momentum(df, date_col, id_col, ret_col):
    df = df.sort_values([id_col, date_col])
    df['log_ret'] = np.log(1 + df[ret_col])
    df['momentum'] = (df.groupby(id_col)['log_ret']
                        .transform(lambda x: x.shift(2).rolling(11).sum()))
    return df
```

---

## 行业分类

**申万行业（推荐）**：
- CSMAR：`TRD_Co.Nnindcd`（细分行业代码）
- 中文名：`TRD_Co.Nnindnme`
- 通常使用**一级行业**（28个或31个行业）
- 行业代码前2位为一级行业代码

**证监会行业（CSRC 2012）**：
- 代码：字母+数字（如 C=制造业，J=金融）
- 通过 `TRD_Co.Indcd` 获取

---

## 文本数据获取

### 上市公司公告
- **CSMAR**：`STK_ANNOUCE`（公告全文）
- **巨潮资讯**：cninfo.com.cn（免费下载）
- **东方财富**：eastmoney.com（爬虫）

### 新闻/媒体报道
- **Tushare**：`pro.news()`（财经新闻）
- **Wind**：新闻数据库
- **自行爬取**：财联社、东方财富股吧、同花顺等

### 分析师报告
- CSMAR CNRDS数据库（部分高校有）
- Wind研报数据库

---

## 数据处理的常见问题

**Q：下载的CSMAR数据为什么有很多NaN？**
A：正常现象。股票在某些月份停牌、退市或未上市，自然没有数据。处理：dropna(subset=['Mretwd'])

**Q：ST股如何过滤？**
```python
# 从股票名称中过滤（需要Tushare或Wind的历史股票名称数据）
# 更简单：用CSMAR TRD_Co中的 Stknme 字段判断
df = df[~df['Stknme'].str.contains('ST', na=False)]
```

**Q：市值单位是什么？**
A：CSMAR中 Msmvttl 单位为**万元**，计算时注意单位统一

**Q：如何对齐季度因子和月度收益？**
A：季度因子（如Q1=2013Q1）对应的持有期收益为 Q+k 季度（如Q+3=2013Q4）内的月度收益（即2013年10、11、12月的收益率）
