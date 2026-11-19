import os
import io
import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from parser import parse_price_text
from storage import init_db, save_quote, get_all_comparison, get_best_supplier, clear_quotes

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 မင်္ဂလာပါ! **Phone Price Comparison Bot** မှ ကြိုဆိုပါတယ်။\n\n"
        "📌 **အသုံးပြုနိုင်သော Command များ:**\n"
        "• `/compare` — လက်ရှိ သိမ်းထားသော ဈေးနှုန်းနှိုင်းယှဉ်ချက် ကြည့်ရန်\n"
        "• `/best <ပစ္စည်းအမည်>` — ဥပမာ `/best K100 Pro Black` (အသက်သာဆုံးဆိုင် ရှာရန်)\n"
        "• `/clear` — သိမ်းထားသော စာရင်းများ ရှင်းထုတ်ရန်\n\n"
        "📝 **ဈေးစာရင်း ပို့ရန်:** စာ၏ ထိပ်ဆုံးတွင် ဆိုင်အမည် ထည့်ပို့ပေးပါ (ဥပမာ - `LK Mobile`)"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def best_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ မော်ဒယ်အမည် ထည့်သွင်းပေးပါ။\nဥပမာ — `/best K100 Pro Black`")
        return
    
    res = get_best_supplier(query)
    if not res:
        await update.message.reply_text(f"❌ '{query}' နှင့် ကိုက်ညီသော ပစ္စည်း ရှာမတွေ့ပါခင်ဗျာ။")
        return
    
    reply = (
        f"📱 **{res['model']} ({res['ram_storage']})**\n\n"
        f"🏆 **ဈေးအသက်သာဆုံး ဆိုင်:** **{res['cheapest_supplier']}**\n"
        f"💰 အနိမ့်ဆုံးဈေး: **{res['lowest_price']:,} MMK**\n"
    )
    if res.get('savings') and res['savings'] > 0:
        reply += f"✨ ဒုတိယဈေးထက် **{res['savings']:,} MMK သက်သာပါသည်**\n"
    
    reply += "\n📊 **ဆိုင်အလိုက် ဈေးနှုန်းများ:**\n"
    for s_name, s_price in res.get('all_prices', {}).items():
        reply += f"• {s_name}: {s_price:,} MMK\n"
    
    reply += "\n⚠️ _Banking ဖြင့် ပေးချေမည့် base ဈေးနှုန်းဖြစ်ပြီး Stock နှင့် Warranty ကို ဝယ်မီ အတည်ပြုပါ_"
    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

async def compare_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_all_comparison()
    if not rows:
        await update.message.reply_text("⚠️ နှိုင်းယှဉ်ရန် ဒေတာ မရှိသေးပါခင်ဗျာ။ ဈေးစာရင်းများ အရင် ပို့ပေးပါ။")
        return
    
    text = "📊 **ဖုန်းဈေးနှုန်း အကျဉ်းချုပ် နှိုင်းယှဉ်ချက်**\n\n"
    for r in rows[:15]:
        text += f"• **{r['model']} ({r['ram_storage']})** 👉 **{r['cheapest_supplier']}** ({r['lowest_price']:,} Ks)"
        if r.get('savings') and r['savings'] > 0:
            text += f" | {r['savings']:,} သက်သာ\n"
        else:
            text += "\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text or text.startswith("/"):
        return
    
    lines = text.strip().split("\n")
    first_line = lines[0].strip()
    supplier = "Supplier C"
    if any(s.lower() in first_line.lower() for s in ["lk", "sky", "supplier", "mobile", "shop"]):
        supplier = first_line.replace("Supplier:", "").replace("Shop:", "").strip()
        text_body = "\n".join(lines[1:])
    else:
        text_body = text

    items = parse_price_text(text_body, supplier)
    if not items:
        return
    
    saved_count = 0
    for it in items:
        save_quote(
            supplier=supplier,
            model=it.get("model"),
            ram_storage=it.get("ram_storage"),
            color=it.get("color"),
            region=it.get("region"),
            price=it.get("price"),
            stock_status=it.get("stock_status", "instock"),
            raw_text=it.get("raw_text", "")
        )
        saved_count += 1
    
    await update.message.reply_text(
        f"✅ **{supplier}** ထံမှ ပစ္စည်း **{saved_count}** မျိုးကို မှတ်သားပြီးပါပြီ။",
        parse_mode=ParseMode.MARKDOWN
    )

def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is not set.")
        return
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("best", best_cmd))
    app.add_handler(CommandHandler("compare", compare_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
