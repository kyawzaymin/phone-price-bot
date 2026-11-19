import os
import io
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)

from parser import parse_price_text, parse_image_with_vision
from storage import init_db, save_quote, get_all_comparison, get_best_supplier, clear_quotes
from excel_export import generate_comparison_excel

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 ဈေးနှုန်းအားလုံး နှိုင်းယှဉ်ချက်", callback_data="btn_compare")],
        [
            InlineKeyboardButton("🔥 K100 Pro", callback_data="quick_K100 Pro"),
            InlineKeyboardButton("🔥 Note 17", callback_data="quick_Note 17"),
            InlineKeyboardButton("🔥 CIVI 3", callback_data="quick_Civi 3")
        ],
        [
            InlineKeyboardButton("🔥 A7 Pro", callback_data="quick_A7 Pro"),
            InlineKeyboardButton("🔥 Note 15 Pro", callback_data="quick_Note 15 Pro"),
            InlineKeyboardButton("🔥 Redmi 17C", callback_data="quick_17C")
        ],
        [InlineKeyboardButton("📄 Excel (.xlsx) ဇယား ထုတ်ယူရန်", callback_data="btn_export")],
        [InlineKeyboardButton("🗑️ စာရင်းများ ရှင်းထုတ်ရန်", callback_data="btn_clear")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 မင်္ဂလာပါ! **Phone Purchase Advisor Bot** မှ ကြိုဆိုပါတယ်။\n\n"
        "အောက်ပါ **ခလုတ်များကို နှိပ်၍** လွယ်ကူစွာ အသုံးပြုနိုင်ပါသည် 👇\n\n"
        "📷 **ဈေးစာရင်း ပို့ရန်:** ဓာတ်ပုံ သို့မဟုတ် စာသားကို Caption တွင် ဆိုင်အမည် (`LK Mobile` / `Sky Mobile`) တပ်၍ ပို့ပေးပါ။"
    )
    if update.message:
        await update.message.reply_text(msg, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
    elif update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "btn_compare":
        await send_comparison(query.message)
    elif data == "btn_export":
        await send_excel(query.message)
    elif data == "btn_clear":
        clear_quotes()
        await query.message.reply_text("🗑️ သိမ်းဆည်းထားသော ဈေးစာရင်းများ အားလုံးကို ရှင်းလင်းပြီးပါပြီ။", reply_markup=get_main_keyboard())
    elif data.startswith("quick_"):
        model_name = data.replace("quick_", "")
        await check_best_and_reply(query.message, model_name)

async def check_best_and_reply(target_message, query_text):
    res = get_best_supplier(query_text)
    if not res:
        await target_message.reply_text(f"❌ '{query_text}' နှင့် ကိုက်ညီသော ပစ္စည်း မတွေ့ပါခင်ဗျာ။ စာရင်းများ အရင် ပို့ပေးပါ။", reply_markup=get_main_keyboard())
        return

    reply = (
        f"📱 **{res['model']} ({res['ram_storage']})**\n"
        f"🎨 အရောင်: {res.get('color', 'Standard')} | 🌐 {res.get('region', 'Standard')}\n\n"
        f"🏆 **ဈေးအသက်သာဆုံး ဆိုင်:** 👉 **{res['cheapest_supplier']}**\n"
        f"💰 အနိမ့်ဆုံးဈေး: **{res['lowest_price']:,} MMK**\n"
    )
    if res.get('savings') and res['savings'] > 0:
        reply += f"✨ ဒုတိယဈေးထက် **{res['savings']:,} MMK သက်သာပါသည်**\n"

    reply += "\n📊 **ဆိုင်အလိုက် ဈေးနှုန်းများ:**\n"
    for s_name, s_price in res.get('all_prices', {}).items():
        if isinstance(s_price, (int, float)):
            reply += f"• {s_name}: {s_price:,} MMK\n"
        else:
            reply += f"• {s_name}: {s_price}\n"

    reply += "\n⚠️ _Banking ဖြင့် ပေးချေမည့် base ဈေးနှုန်းဖြစ်ပြီး Stock နှင့် Warranty ကို ဝယ်မီ အတည်ပြုပါ_"
    await target_message.reply_text(reply, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def send_comparison(target_message):
    rows = get_all_comparison()
    if not rows:
        await target_message.reply_text("⚠️ နှိုင်းယှဉ်ရန် ဒေတာ မရှိသေးပါခင်ဗျာ။ ဈေးစာရင်းများ အရင် ပို့ပေးပါ။", reply_markup=get_main_keyboard())
        return

    text = "📊 **ဖုန်းဈေးနှုန်း အကျဉ်းချုပ် နှိုင်းယှဉ်ချက်**\n\n"
    for r in rows[:15]:
        text += f"• **{r['model']} ({r['ram_storage']})** 👉 **{r['cheapest_supplier']}** ({r['lowest_price']:,} Ks)"
        if r.get('savings') and r['savings'] > 0:
            text += f" | {r['savings']:,} သက်သာ\n"
        else:
            text += "\n"

    if len(rows) > 15:
        text += f"\n_... စုစုပေါင်း {len(rows)} မျိုး ရှိပါသည်။ အပြည့်အစုံကို Excel ဖြင့် ထုတ်ယူနိုင်ပါသည်_"

    await target_message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def send_excel(target_message):
    await target_message.reply_text("📄 Excel (.xlsx) ဖိုင်ကို ပြုစုထုတ်ပေးနေပါသည်...")
    excel_bytes = generate_comparison_excel()
    await target_message.reply_document(
        document=io.BytesIO(excel_bytes),
        filename="Supplier_Price_Comparison.xlsx",
        caption="📊 **Supplier Price Comparison Report**\n(Comparison, Quantity Prices, Source Quotes & Notes ပါဝင်ပါသည်)"
    )

async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption or ""
    supplier = "Supplier (Image)"
    if caption:
        for s in ["LK Mobile", "Sky Mobile", "Supplier C"]:
            if s.lower() in caption.lower():
                supplier = s
                break
        if supplier == "Supplier (Image)":
            supplier = caption.strip().split("\n")[0]

    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    image_bytes = await photo_file.download_as_bytearray()

    await update.message.reply_text(f"🔍 **{supplier}** ၏ ဈေးစာရင်း ဓာတ်ပုံကို ဖတ်ရှုစစ်ဆေးနေပါသည်...")
    items = parse_image_with_vision(image_bytes, supplier)
    
    if not items:
        await update.message.reply_text(
            f"⚠️ ဓာတ်ပုံထဲမှ စာသားဖတ်၍ မရပါ (သို့မဟုတ် GEMINI_API_KEY မသတ်မှတ်ရသေးပါ)။\n"
            f"ကျေးဇူးပြု၍ စာသားဖြင့် ပို့ပေးပါရန် မေတ္တာရပ်ခံပါသည်။",
            reply_markup=get_main_keyboard()
        )
        return

    saved_count = 0
    for it in items:
        save_quote(
            supplier=supplier,
            model=it.get("model"),
            ram_storage=it.get("ram_storage"),
            color=it.get("color", "Standard"),
            region=it.get("region", "Standard"),
            price=it.get("price"),
            stock_status=it.get("stock_status", "instock"),
            raw_text=it.get("raw_text", "")
        )
        saved_count += 1

    await update.message.reply_text(
        f"✅ ဓာတ်ပုံထဲမှ **{supplier}** ၏ ပစ္စည်း **{saved_count}** မျိုးကို အောင်မြင်စွာ ဖတ်ယူသိမ်းဆည်းပြီးပါပြီ။",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

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
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def best_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("⚠️ မော်ဒယ်အမည် ထည့်သွင်းပေးပါ။\nဥပမာ — `/best K100 Pro Black`", reply_markup=get_main_keyboard())
        return
    await check_best_and_reply(update.message, query)

async def compare_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_comparison(update.message)

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_excel(update.message)

def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is not set.")
        return
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("best", best_cmd))
    app.add_handler(CommandHandler("compare", compare_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("Bot is running with Buttons and Image OCR...")
    app.run_polling()

if __name__ == "__main__":
    main()
