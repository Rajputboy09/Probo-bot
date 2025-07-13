import requests, re, statistics
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

BOT_TOKEN = '7759576897:AAFtSI_IFd73jmSmy9UGD8jtPNSNlmf87cY'  # <--- Replace with your actual bot token

# ------------------- Indicators -------------------

def fetch_candles():
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=50"
    data = requests.get(url).json()
    candles, closes, volumes = [], [], []
    for c in data:
        o, h, l, close, vol = float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])
        candles.append({'open': o, 'high': h, 'low': l, 'close': close})
        closes.append(close)
        volumes.append(vol)
    return candles, closes, volumes

def calc_rsi(closes, period=14):
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i-1]
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))
    if len(gains) < period:
        return 50
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calc_ema(closes, period):
    k = 2 / (period + 1)
    ema = [sum(closes[:period]) / period]
    for price in closes[period:]:
        ema.append((price - ema[-1]) * k + ema[-1])
    return round(ema[-1], 2)

def calc_macd(closes):
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    return round(ema12 - ema26, 2)

def detect_trap(candles):
    for c in candles[-3:]:
        wick_pct = ((c['high'] - c['close']) / c['high']) * 100 if c['high'] != 0 else 0
        if 40 <= wick_pct <= 80 and c['close'] < c['high']:
            return True
    return False

def detect_volume_spike(volumes):
    avg = statistics.mean(volumes[:-1])
    return volumes[-1] > 1.5 * avg

# ------------------- Format Detector -------------------

def parse_target_question(text):
    match = re.search(r'BTC.*?([\d.]+).*?at (\d{1,2}:\d{2}) ?(AM|PM)?', text, re.IGNORECASE)
    if match:
        price = float(match.group(1))
        time = match.group(2) + (" " + match.group(3) if match.group(3) else "")
        return price, time.strip()
    return None, None

# ------------------- Response Builder -------------------

def indicator_report(closes, candles, volumes):
    current = closes[-1]
    rsi = calc_rsi(closes)
    macd = calc_macd(closes)
    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    trap = detect_trap(candles)
    volume = detect_volume_spike(volumes)
    trend = "Bullish" if ema9 > ema21 else "Bearish"
    return {
        'price': round(current, 2),
        'rsi': rsi,
        'macd': macd,
        'ema9': ema9,
        'ema21': ema21,
        'trap': trap,
        'volume_spike': volume,
        'trend': trend
    }

def calculate_confidence(report):
    score = 0
    score += 1 if report['rsi'] > 50 else 0
    score += 1 if report['macd'] > 0 else 0
    score += 1 if report['ema9'] > report['ema21'] else 0
    score += 1 if not report['trap'] else 0
    score += 1 if report['volume_spike'] else 0
    return score * 20

def generate_prediction_output(report, target, time_str):
    confidence = calculate_confidence(report)
    prediction = "✅ YES — likely to cross" if confidence >= 60 else "❌ NO — unlikely to cross"
    buffer = 30
    up_price = round(target + buffer, 2)
    down_price = round(target - buffer, 2)
    return (
        f"📊 BTC Price Prediction\n\n"
        f"🎯 Target: {target} by {time_str}\n"
        f"💰 Current Price: {report['price']}\n\n"
        f"📉 Trend: {report['trend']}\n"
        f"📊 RSI: {report['rsi']}\n"
        f"📈 MACD: {report['macd']}\n"
        f"📉 EMA9: {report['ema9']} | EMA21: {report['ema21']}\n"
        f"⚠️ Trap Detected: {'✅' if report['trap'] else '❌'}\n"
        f"🎯 Confidence: {confidence}%\n\n"
        f"🤖 Prediction: {prediction}\n"
        f"📢 Bet YES if price crosses above: {up_price}\n"
        f"📢 Bet NO if price stays below: {down_price}"
    )

def generate_pro_signal_output(report):
    confidence = calculate_confidence(report)
    direction = "UP" if report['trend'] == "Bullish" and report['rsi'] > 50 and report['macd'] > 0 else "DOWN"
    entry = round(report['price'] + 30, 2) if direction == "UP" else round(report['price'] - 30, 2)
    buffer = 30
    upper = entry
    lower = round(report['price'] - buffer, 2) if direction == "UP" else round(report['price'] + buffer, 2)
    return (
        f"📈 BTC PRO SIGNAL\n\n"
        f"💰 Current Price: {report['price']}\n\n"
        f"📊 Indicators:\n"
        f"{'✅' if report['rsi'] > 50 else '❌'} RSI: {report['rsi']}\n"
        f"{'✅' if report['macd'] > 0 else '❌'} MACD: {report['macd']}\n"
        f"{'✅' if report['ema9'] > report['ema21'] else '❌'} EMA9: {report['ema9']} | EMA21: {report['ema21']} → Trend: {report['trend']}\n"
        f"{'✅' if report['trap'] else '❌'} Trap Candle: {'Yes' if report['trap'] else 'No'}\n"
        f"{'✅' if report['volume_spike'] else '❌'} Volume Spike: {'Yes' if report['volume_spike'] else 'No'}\n\n"
        f"🎯 Suggested Trade:\n"
        f"→ Direction: {direction}\n"
        f"→ Entry {'above' if direction=='UP' else 'below'} {entry}\n"
        f"🔒 Confidence: {confidence}%\n\n"
        f"📢 Probo Bet Guide:\n"
        f"{'✅ Bet YES if BTC crosses ' + str(upper)}\n"
        f"{'❌ Bet NO if BTC stays below ' + str(lower)}" if direction == "UP"
        else f"✅ Bet YES if BTC drops below {upper}\n❌ Bet NO if BTC stays above {lower}"
    )

# ------------------- Telegram Bot -------------------

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    target_price, time_str = parse_target_question(text)

    candles, closes, volumes = fetch_candles()
    report = indicator_report(closes, candles, volumes)

    if target_price and time_str:
        msg = generate_prediction_output(report, target_price, time_str)
    else:
        msg = generate_pro_signal_output(report)

    await update.message.reply_text(msg)

# ------------------- Start Bot -------------------

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
print("✅ Bot is running...")
app.run_polling()
