import sys
import os
import pandas as pd
import yfinance as yf
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

class SuppressStderr:
    def __enter__(self):
        self._original_stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr.close()
        sys.stderr = self._original_stderr

def get_candlestick_pattern(df_last3):
    c1 = df_last3.iloc[0]
    c2 = df_last3.iloc[1]
    c3 = df_last3.iloc[2]

    o1, h1, l1, c1_close = float(c1['Open']), float(c1['High']), float(c1['Low']), float(c1['Close'])
    o2, h2, l2, c2_close = float(c2['Open']), float(c2['High']), float(c2['Low']), float(c2['Close'])
    o3, h3, l3, c3_close = float(c3['Open']), float(c3['High']), float(c3['Low']), float(c3['Close'])

    b1, range1 = abs(c1_close - o1), (h1 - l1)
    b2, range2 = abs(c2_close - o2), (h2 - l2)
    b3, range3 = abs(c3_close - o3), (h3 - l3)

    green1, red1 = c1_close > o1, c1_close < o1
    green2, red2 = c2_close > o2, c2_close < o2
    green3, red3 = c3_close > o3, c3_close < o3

    if green1 and green2 and green3 and c3_close > c2_close > c1_close and o3 > o2 > o1:
        return "Three White Soldiers 🟢🟢🟢 (Bullish Kuat)"
    if red1 and red2 and red3 and c3_close < c2_close < c1_close and o3 < o2 < o1:
        return "Three Black Crows 🔴🔴🔴 (Bearish Kuat)"
    if red1 and (b2 / range2 <= 0.3 if range2 > 0 else True) and green3 and c3_close >= (o1 + c1_close) / 2:
        return "Morning Star 🟢 (Pembalikan Arah Naik)"
    if green1 and (b2 / range2 <= 0.3 if range2 > 0 else True) and red3 and c3_close <= (o1 + c1_close) / 2:
        return "Evening Star 🔴 (Pembalikan Arah Turun)"
    if red1 and green2 and c2_close > o1 and green3 and c3_close > c2_close:
        return "Three Inside Up 🟢 (Konfirmasi Pembalikan Naik)"
    if green1 and red2 and c2_close < o1 and red3 and c3_close < c2_close:
        return "Three Inside Down 🔴 (Konfirmasi Pembalikan Turun)"

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
    if upper_shade3 >= 2 * b3 and lower_shade3 <= 0.2 * b3:
        return "Inverted Hammer 🟢 (Potensi Naik)" if green3 else "Shooting Star 🔴 (Potensi Turun)"
    if range3 > 0 and b3 / range3 >= 0.8:
        return "Bullish Marubozu 🟢 (Beli Sangat Kuat)" if green3 else "Bearish Marubozu 🔴 (Jual Sangat Kuat)"

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
            df = t.history(period='3mo')
        
        if df.empty or len(df) < 50:
            return f"❌ Data tidak cukup atau kode saham salah: {ticker}"

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

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
        close_1m_ago = float(df_1m.iloc[0]['Close'])
        high_1m = float(df_1m['High'].max())
        low_1m = float(df_1m['Low'].min())

        close = float(last['Close'])
        prev_close = float(prev['Close'])
        high_today = float(last['High'])
        low_today = float(last['Low'])
        ma5 = float(last['MA5'])
        ma20 = float(last['MA20'])
        ma50 = float(last['MA50'])
        rsi_today = float(last['RSI'])
        stoch_k = float(last['%K'])
        stoch_d = float(last['%D'])
        vol_today = float(last['Volume'])
        vol_yesterday = float(prev['Volume'])
        vol_ma20 = float(last['Vol_MA20'])
        vol_ratio = (vol_today / vol_ma20) if vol_ma20 > 0 else 1.0

        change_1d = ((close - prev_close) / prev_close) * 100
        change_1m = ((close - close_1m_ago) / close_1m_ago) * 100

        candle_pattern = get_candlestick_pattern(df.tail(3))
        clean_ticker = ticker.replace('.JK', '')

        msg = f"==========================================\n" \
              f"   ANALISIS TEKNIKAL SAHAM: {clean_ticker}\n" \
              f"==========================================\n\n" \
              f"1. RINGKASAN DATA HARI INI\n" \
              f"   Harga Terakhir : Rp{int(round(close)):,} ({change_1d:+.2f}%)\n" \
              f"   High / Low 1D  : Rp{int(round(high_today)):,} / Rp{int(round(low_today)):,}\n" \
              f"   Pola 3 Candle  : {candle_pattern}\n" \
              f"   Volume Hari Ini: {int(vol_today):,} lembar\n" \
              f"   Volume Kemarin : {int(vol_yesterday):,} lembar\n" \
              f"   Perubahan 1M   : {change_1m:+.2f}% (dari Rp{int(round(close_1m_ago)):,})\n" \
              f"   High / Low 1M  : Rp{int(round(high_1m)):,} / Rp{int(round(low_1m)):,}\n" \
              f"   MA5  (Mingguan): Rp{int(round(ma5)):,}\n" \
              f"   MA20 (Bulanan) : Rp{int(round(ma20)):,}\n" \
              f"   MA50 (2.5 Bln) : Rp{int(round(ma50)):,}\n\n" \
              f"2. ANALISIS TREN & OSCILLATOR\n" \
              f"   Tren Utama : {'Bullish Kuat' if change_1m > 10 else ('Bullish Moderat' if change_1m > 0 else 'Konsolidasi/Bearish')} (+{change_1m:.2f}%)\n" \
              f"   Struktur MA: {'Bullish (MA5 > MA20 > MA50)' if ma5 > ma20 > ma50 else ('Pembalikan Arah (MA5 > MA20)' if ma5 > ma20 else 'Tren Melemah (MA5 < MA20)')}\n" \
              f"   RSI (14)   : {rsi_today:.1f} - {'🔴 Overbought' if rsi_today >= 70 else ('🟢 Oversold' if rsi_today <= 30 else '🟡 Netral')}\n" \
              f"   Stochastic : %K {stoch_k:.1f} / %D {stoch_d:.1f} - {'🔴 Overbought' if stoch_k >= 80 else ('🟢 Oversold' if stoch_k <= 20 else '🟡 Netral')}\n\n" \
              f"3. INDIKATOR VOLUMETRIK & FLOW\n" \
              f"   Vol MA20      : {int(vol_ma20):,} (Rata-rata Bulanan)\n" \
              f"   Rasio Volume  : {vol_ratio:.2f}x rata-rata\n" \
              f"   Status Flow   : {'🟢 AKUMULASI BESAR (High Volume Buying)' if vol_ratio >= 1.5 and change_1d > 0 else ('🔴 DISTRIBUSI BESAR (High Volume Selling)' if vol_ratio >= 1.5 and change_1d < 0 else ('⚪ VOLUME SEPI (Konsolidasi/Sepi Transaksi)' if vol_ratio < 0.8 else '🟡 NORMAL (Transaksi Stabil)'))}\n\n" \
              f"4. TRADING PLAN\n" \
              f"   Strategi  : Buy on Weakness\n" \
              f"   Area Beli : Rp{int(round(min(ma20, ma5 * 0.98))):,} - Rp{int(round(ma5)):,}\n" \
              f"   Target 1  : Rp{int(round(close * 1.05)):,} (+5%)\n" \
              f"   Target 2  : Rp{int(round(close * 1.10)):,} (+10%)\n" \
              f"   Stop Loss : Rp{int(round(ma20 * 0.98)):,} (Di bawah MA20)\n" \
              f"=========================================="
        return msg
    except Exception as e:
        return f"❌ Terjadi kesalahan saat memproses saham {ticker_symbol}: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! 🚀 Selamat datang di Bot Analisis Saham IHSG.\n\n"
        "Ketik kode saham yang ingin dianalisis (Contoh: `BBCA`, `TLKM`, `ASII`)."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    await update.message.reply_text(f"Sedang menganalisis saham {text.upper()}... Mohon tunggu sebentar ⏳")
    result = analyze_stock_text(text)
    formatted_msg = f"```\n{result}\n```"
    await update.message.reply_text(formatted_msg, parse_mode='Markdown')

def main():
    TOKEN = "8974078062:AAG0zXuy9XJ2nl_zmKfry72BU7WnzX3TZ_o"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot Telegram sedang berjalan... Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == "__main__":
    main()
