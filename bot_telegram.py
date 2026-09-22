import sys
import os
import math
from datetime import datetime
import pandas as pd
import yfinance as yf
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Token bot baru Anda sudah terpasang di sini
TOKEN = "8983964996:AAH3Yc60YWJZYO2nGRasuMWjKEH8huFU8x8"

class SuppressStderr:
    def __enter__(self):
        self._original_stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr.close()
        sys.stderr = self._original_stderr

def safe_float(val, default=0.0):
    try:
        if val is None or pd.isna(val) or math.isnan(float(val)):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default

def safe_int(val, default=0):
    try:
        f = safe_float(val, default)
        if math.isnan(f):
            return default
        return int(round(f))
    except (ValueError, TypeError):
        return default

def get_candlestick_pattern(df_last3):
    if len(df_last3) < 3:
        return "Data Candle Kurang 🟡"
    
    c1 = df_last3.iloc[0]
    c2 = df_last3.iloc[1]
    c3 = df_last3.iloc[2]

    o1, h1, l1, c1_close = safe_float(c1['Open']), safe_float(c1['High']), safe_float(c1['Low']), safe_float(c1['Close'])
    o2, h2, l2, c2_close = safe_float(c2['Open']), safe_float(c2['High']), safe_float(c2['Low']), safe_float(c2['Close'])
    o3, h3, l3, c3_close = safe_float(c3['Open']), safe_float(c3['High']), safe_float(c3['Low']), safe_float(c3['Close'])

    b1, range1 = abs(c1_close - o1), (h1 - l1)
    b2, range2 = abs(c2_close - o2), (h2 - l2)
    b3, range3 = abs(c3_close - o3), (h3 - l3)

    green1, red1 = c1_close > o1, c1_close < o1
    green2, red2 = c2_close > o2, c2_close < o2
    green3, red3 = c3_close > o3, c3_close < o3

    if green1 and green2 and green3 and c3_close > c2_close > c1_close and o3 > o2 > o1:
        return "Three White Soldiers 🟢 (Bullish Kuat)"
    if red1 and red2 and red3 and c3_close < c2_close < c1_close and o3 < o2 < o1:
        return "Three Black Crows 🔴 (Bearish Kuat)"
    if red1 and (b2 / range2 <= 0.3 if range2 > 0 else True) and green3 and c3_close >= (o1 + c1_close) / 2:
        return "Morning Star 🟢 (Pembalikan Naik)"
    if green1 and (b2 / range2 <= 0.3 if range2 > 0 else True) and red3 and c3_close <= (o1 + c1_close) / 2:
        return "Evening Star 🔴 (Pembalikan Turun)"
    
    upper_shade3 = h3 - max(o3, c3_close)
    lower_shade3 = min(o3, c3_close) - l3

    if range3 > 0 and b3 / range3 <= 0.1:
        return "Doji 🟡 (Konsolidasi/Netral)"
    if green3 and red2 and o3 <= c2_close and c3_close >= o2:
        return "Bullish Engulfing 🟢 (Sinyal Naik)"
    if red3 and green2 and o3 >= c2_close and c3_close <= o2:
        return "Bearish Engulfing 🔴 (Sinyal Turun)"
    if lower_shade3 >= 2 * b3 and upper_shade3 <= 0.2 * b3:
        return "Hammer 🟢 (Potensi Naik)" if green3 else "Hanging Man 🔴 (Potensi Turun)"

    if c3_close > c2_close > c1_close:
        return "Tren Naik 3 Hari 🟢"
    elif c3_close < c2_close < c1_close:
        return "Tren Turun 3 Hari 🔴"

    return "Bullish Candle 🟢" if green3 else ("Bearish Candle 🔴" if red3 else "Netral 🟡")

def analyze_stock_text(ticker_symbol):
    ticker = ticker_symbol.upper().strip()
    if not ticker.endswith('.JK'):
        ticker += '.JK'
        
    try:
        with SuppressStderr():
            t = yf.Ticker(ticker)
            df = t.history(period='3mo', auto_adjust=False)
        
        if df is None or df.empty:
            return f"❌ Data kosong untuk kode saham: {ticker}"

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df.columns = [str(col).capitalize() for col in df.columns]
        df = df.dropna(subset=['Close'])

        if len(df) < 30:
            return f"❌ Data historis tidak cukup (< 30 hari): {ticker}"

        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()

        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        low14 = df['Low'].rolling(window=14).min()
        high14 = df['High'].rolling(window=14).max()
        df['%K'] = ((df['Close'] - low14) / (high14 - low14)) * 100
        df['%D'] = df['%K'].rolling(window=3).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]
        df_1m = df.tail(20)
        close_1m_ago = safe_float(df_1m.iloc[0]['Close'])

        close = safe_float(last['Close'])
        prev_close = safe_float(prev['Close'])
        high_today = safe_float(last['High'])
        low_today = safe_float(last['Low'])
        vol_today = safe_float(last['Volume'])
        vol_yesterday = safe_float(prev['Volume'])
        
        ma5 = safe_float(last['MA5'], close)
        ma20 = safe_float(last['MA20'], close)
        ma50 = safe_float(last['MA50'], close)
        
        rsi_today = safe_float(last['RSI'], 50.0)
        stoch_k = safe_float(last['%K'], 50.0)
        stoch_d = safe_float(last['%D'], 50.0)
        
        vol_ma20 = safe_float(last['Vol_MA20'], 1.0)
        vol_ratio = (vol_today / vol_ma20) if vol_ma20 > 0 else 1.0

        change_1d = (((close - prev_close) / prev_close) * 100) if prev_close > 0 else 0.0
        change_1m = (((close - close_1m_ago) / close_1m_ago) * 100) if close_1m_ago > 0 else 0.0

        candle_pattern = get_candlestick_pattern(df.tail(3))
        clean_ticker = ticker.replace('.JK', '')

        buy_area_min = safe_int(min(ma20, ma5 * 0.98) if ma20 > 0 and ma5 > 0 else close * 0.98)
        buy_area_max = safe_int(ma5 if ma5 > 0 else close)
        target_1 = safe_int(close * 1.05)
        target_2 = safe_int(close * 1.10)
        stop_loss = safe_int(ma20 * 0.98 if ma20 > 0 else close * 0.95)

        rsi_status = "Overbought 🔴" if rsi_today >= 70 else ("Oversold 🟢" if rsi_today <= 30 else "Netral 🟡")
        stoch_status = "Overbought 🔴" if stoch_k >= 80 else ("Oversold 🟢" if stoch_k <= 20 else "Netral 🟡")
        
        if vol_ratio >= 1.5:
            if change_1d > 0:
                status_flow = "🟢 AKUMULASI BESAR (Buyer Dominan & Volume Tinggi)"
            else:
                status_flow = "🔴 DISTRIBUSI BESAR (Tekanan Jual & Volume Tinggi)"
        else:
            status_flow = "⚪ VOLUME NORMAL/SEPI (Konsolidasi Pasar)"

        if change_1m > 10:
            trend_utama = f"Bullish Kuat 🟢 ({change_1m:+.2f}%)"
        elif change_1m > 0:
            trend_utama = f"Bullish Moderat 🟢 ({change_1m:+.2f}%)"
        else:
            trend_utama = f"Konsolidasi/Bearish 🔴 ({change_1m:+.2f}%)"
            
        ma_struct = "Tren Menguat (MA5 > MA20)" if ma5 > ma20 else "Tren Melemah (MA5 < MA20)"

        current_time_str = datetime.now().strftime('%d-%m-%Y %H:%M:%S WIB')

        msg = f"""========================================
ANALISIS TEKNIKAL SAHAM: {clean_ticker}
Waktu Analisis : {current_time_str}
Status Data    : ⚠️ Delay 10-15 Menit (Sumber: Yahoo Finance)
========================================

1. RINGKASAN DATA HARI INI
   Harga Terakhir : Rp{safe_int(close):,} ({change_1d:+.2f}%)
   High / Low 1D  : Rp{safe_int(high_today):,} / Rp{safe_int(low_today):,}
   Pola 3 Candle  : {candle_pattern}
   Volume Hari Ini: {safe_int(vol_today):,} lembar
   Volume Kemarin : {safe_int(vol_yesterday):,} lembar
   Perubahan 1M   : {change_1m:+.2f}% (dari Rp{safe_int(close_1m_ago):,})
   MA5 (Mingguan) : Rp{safe_int(ma5):,}
   MA20 (Bulanan) : Rp{safe_int(ma20):,}
   MA50 (2.5 Bln) : Rp{safe_int(ma50):,}

2. ANALISIS TREN & OSCILLATOR
   Tren Utama     : {trend_utama}
   Struktur MA    : {ma_struct}
   RSI (14)       : {rsi_today:.1f} - {rsi_status}
   Stochastic     : %K {stoch_k:.1f} / %D {stoch_d:.1f} - {stoch_status}

3. INDIKATOR VOLUMETRIK & FLOW
   Vol MA20       : {safe_int(vol_ma20):,} (Rata-rata Bulanan)
   Rasio Volume   : {vol_ratio:.2f}x rata-rata
   Status Flow    : {status_flow}

4. TRADING PLAN
   Strategi       : Buy on Weakness
   Area Beli      : Rp{buy_area_min:,} - Rp{buy_area_max:,}
   Target 1       : Rp{target_1:,} (+5%)
   Target 2       : Rp{target_2:,} (+10%)
   Stop Loss      : Rp{safe_int(stop_loss):,} (Di bawah MA20)
========================================"""
        return f"```\n{msg}\n```"
    except Exception as e:
        return f"❌ Terjadi kesalahan saat memproses {ticker_symbol}: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Selamat datang di Bot Analisis Saham IHSG.\n\n"
        "Kirimkan kode saham yang ingin dianalisis (contoh: `BBCA`, `BMRI`, `AYLS`)."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        return
    
    ticker = text.split()[0]
    await update.message.reply_text(f"⏳ Sedang menganalisis saham {ticker.upper()}...\nMohon tunggu sebentar ⏳")
    
    result = analyze_stock_text(ticker)
    await update.message.reply_text(result, parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🤖 Bot Telegram sedang berjalan...")
    app.run_polling()

if __name__ == '__main__':
    main()
