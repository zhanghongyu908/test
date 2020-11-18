﻿
from operator import itemgetter, attrgetter
import pandas as pd
import numpy as np
import talib as tl
## 初始化函数，设定要操作的股票、基准等等

    g.buylist=[]
    # 持仓数量
    g.stocknum =10
    # 持仓天数
    g.holdDays=[]
    for days in range(0,7):
        g.holdDays.append([])

    # 股票买入金额 
    g.cash_per_stock = context.portfolio.portfolio_value / g.stocknum
    # 运行函数
    # run_daily(trade,time="open")
    # 止盈百分比
    g.cut_gain_percentage = 0.2
    # 止损百分比
    g.cut_loss_percentage = 0.5
 
## 形态和成交额选股
def check_stocks(context):
# 设定查询条件
    q = query(
            valuation.code,
            valuation.circulating_market_cap,
            valuation.circulating_cap
        ).filter(
            valuation.circulating_market_cap.between(8,50)
        ).order_by(
            valuation.circulating_market_cap.asc()
        )
    # 选股
    df = get_fundamentals(q)
    resultdict=dict()
    buylist=[]
    for index,row in df.iterrows():
        hData = attribute_history(row['code'], 10, unit='1d'
            , fields=['open', 'close', 'high', 'low', 'volume', 'money','high_limit']
            , skip_paused=False
            , df=False)
        closes = hData['close']
        amount = hData['money']
        vl=hData['volume']
        hlm=hData['high_limit']
        lows=hData['low']
        highs=hData['high']
        opens=hData['open']
        if np.isnan(closes[0]):
            continue
        
        if amount[-1]>2200000000:
            continue
        
        if vl[-1]!=max(vl[-3:]):
            continue
        
        if amount[-3]/amount[-4]<2:
            continue
        
        if closes[-1]!=hlm[-1] or closes[-2]!=hlm[-2] or closes[-3]!=hlm[-3] or closes[-4]==hlm[-4]:
            continue
        
        resultdict[row['code']]=closes[-1]
        log.info(row['code'],get_security_info(row['code']).display_name,amount[-1],context.current_dt)
    
    sorteddict=sorted(resultdict.iteritems(), key=itemgetter(1),reverse=False)
    for v in sorteddict:
        buylist.append(v[0])
    g.buylist = filter_paused_stock(buylist)
    
    
def before_trading_start(context):
    check_stocks(context)
    
## 交易函数
def handle_data(context, data):
    if context.current_dt.hour != 9 or  context.current_dt.minute != 30:
        return
    todaylist=[]
    # 如果有持仓，则卖出
    if len(list(context.portfolio.positions.keys())) > 0 :
        to_sell = sell_signal(context)
        for security in to_sell[1]:
            order_target(security, 0)
        for security in to_sell[0]:
            order_target(security,0)
    if len(g.holdDays[-1])>0:
        for security in g.holdDays[-1]:
            order_target(security, 0)
    g.holdDays.insert(0,[])
    g.holdDays=g.holdDays[:-1]
    ## 选股
    if len(g.buylist)==0:
        return
    buynum =  g.stocknum - len(context.portfolio.positions.keys())
    if buynum<=0:
        return
    stock_list = g.buylist[:buynum]   
    cash = context.portfolio.portfolio_value /(len(stock_list)+1)
    for stock in stock_list:
        if stock in list(context.portfolio.positions.keys()):
            continue
        if len(context.portfolio.positions.keys()) < g.stocknum:
            close = attribute_history(stock, 1, '1d', ['close'])['close'][0]
            curOpen = get_current_data()[stock].day_open
            if curOpen>=close*0.94:
                order_value(stock, cash)
                todaylist.append(stock)

    g.holdDays[0].extend(todaylist)
     
 
 
 
# 过滤停牌股票
def filter_paused_stock(stock_list):
    cur_data = get_current_data()
    # 非停牌、非ST
    stock_list = [stock for stock in stock_list if 
                  (not cur_data[stock].paused) and 
                  (not cur_data[stock].is_st) and 
                  ('ST' not in cur_data[stock].name) and 
                  ('*' not in cur_data[stock].name) and 
                  ('退' not in cur_data[stock].name)]
    
    return stock_list
 
def sell_signal(context):
    # 建立需要卖出的股票list 
    to_sell_gain = []
    to_sell_lost = []
    # 对于仓内所有股票
    for security in context.portfolio.positions:
        # 取现价
        current_price = attribute_history(security, 1, '1d', ['close'])['close'][0]
        # 获取买入平均价格
        avg_cost = context.portfolio.positions[security].avg_cost
        # 计算止盈线
        high = avg_cost * (1+ g.cut_gain_percentage)
        # 计算止损线
        low = avg_cost*(1-g.cut_loss_percentage)
        # 如果价格突破了止损或止盈线
        if current_price >= high:
            to_sell_gain.append(security)
        if current_price <= low:
            to_sell_lost.append(security)
    return(to_sell_gain,to_sell_lost)
