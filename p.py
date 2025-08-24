import random 
import nest_asyncio
import random
import json
import os
import sys
import base64
import shutil
from io import BytesIO
import aiohttp
from telegram import InputFile
from telegram import Update
from telegram.helpers import mention_html, escape_markdown
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
import logging

# Logger setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
nest_asyncio.apply()

TOKEN = "8482426081:AAFIgfRMBj4KdIqGSlxtjPCbatocUl_Gf-s"
OWNER_USERNAME = "@Problem_Zenki"
OWNER_ID = 7808603044
CHANNEL_ID = -1002153191249  
GROUP_ID = -1001234567890  # သင့် group id
GROUP_ID_FILE = "group_id.txt"
LOG_FILE = "send__command_log.json"

# ဖိုင်မရှိရင် [] နဲ့ စပြီး ဖန်တီးထားမယ်
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

def write_log(entry):
    """log ဖိုင်ထဲကို entry အသစ်ထည့်ရန်"""
    data = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
        except Exception:
            # JSON corrupted ဖြစ်ရင် reset
            data = []

    # အသစ်ထည့်
    data.append(entry)

    # overwrite ပြန်သိမ်း
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # Log write fail ရင် console ထဲမှာပဲ print
        print(f"❌ Log write failed (ignored): {e}")

OWNER_USERNAME_LC = OWNER_USERNAME.lower()

# ====== Owner check (username or user_id support) ======
def is_owner(user) -> bool:
    """
    user: str (username) or int (user_id)
    """
    if isinstance(user, int):
        return user == OWNER_ID
    # assume string username
    username = user.lower()
    owner = OWNER_USERNAME.lower()
    if not username.startswith("@"):
        username = "@" + username
    if not owner.startswith("@"):
        owner = "@" + owner
    return username == owner

# ====== Admin or Owner check (username or user_id support) ======
def is_admin_or_owner(user) -> bool:
    """
    user: str (username) or int (user_id)
    """
    if isinstance(user, int):
        return user in ADMINS or user == OWNER_ID

    # assume string username
    username = user.lower()
    if not username.startswith("@"):
        username = "@" + username

    owner = OWNER_USERNAME.lower()
    if not owner.startswith("@"):
        owner = "@" + owner

    # username ကို owner နဲ့ admin list နှစ်ခုမှာစစ်မယ်
    return username == owner or username in [a.lower() if a.startswith("@") else "@" + a.lower() for a in ADMINS]

GROUP_FILE = "groups.json"

# Group ID တွေကို ဖိုင်ထဲကနေ Load
def load_groups():
    if not os.path.exists(GROUP_FILE):
        return []
    with open(GROUP_FILE, "r") as f:
        return json.load(f)

# Group ID အသစ်စာရင်းလုံးကို overwrite လုပ်
def save_groups(group_ids):
    with open(GROUP_FILE, "w") as f:
        json.dump(group_ids, f)

# Group ID တစ်ခုချင်းစီထည့်ပြီး သိမ်း
def save_group_id(group_id):
    group_ids = load_groups()
    if group_id not in group_ids:
        group_ids.append(group_id)
        save_groups(group_ids)

# Group ID ကို သွင်းဖို့ handler
async def track_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type in ["group", "supergroup"]:
        save_group_id(chat.id)

ADMIN_FILE = "admins.json"

DEFAULT_ADMINS = [
    "@Codra_ricky",
    "@SolveBack",
    "@Joy_fav_Lyushi",
    "@Dbngaduu",
    "@Xnhdsi",
    "@htetaunglin9999999",
    "@ifwemo4",
]

# list -> set ပြောင်းပြီး lowercase ပြောင်း
ADMIN_USERNAMES = {a.lower() for a in DEFAULT_ADMINS}

ADMINS_LC = ADMIN_USERNAMES  # ဒီအတိုင်းသုံးနိုင်ပါတယ်

ACTIVE_ATTACKS = {}
AUTO_DIE = {}
auto_replies = [ "ပြသာနာဆိုတဲ့သခင်ဆဲရင်မင်းတို့ငြိမ်ခံရမယ်ဆိုတာမင်းတို့အမေဖာသည်မကြီးမသင်ပေးထားဘူးလား", "မင်းအဖေကပိုက်ဆံလိုလို့မင်းအမေကိုငါနဲ့ပေးလိုးပြီးမင်းထွက်လာတာလေသားမိုက်", "မင်းစော်ဖာသည်မပေးဘုပါလားလွတ်လိုက်‌ေနာ်အရှင်သခင်ပြသာနာဆီကိုလေ", "မင်းအမေဖာသည်မကိုငါ့ဆီလိင်ကျွန်အဖြစ်ခစားနေရတယ်", "ဘာဘာတောင်းပန်တယ်ဟုတ်လား ခြေထောက်ထိတောင်းပန်လေ", "ဟက်ကလစ်ခွေးမင်းကလစ်ကြီးကနှေးကွေးနေတာဘဲTypingဆိုရင်တော့လိပ်ဂွင်းထုမှပြီးမယ့်ကောင်", "ငါရဲ့စာကိုချေပဖို့မင်းအမေဖာသည်မကြီးကမသင်ပေးထားဘူးလေကွာ", "မင်းစကေးကဒါပဲလားဖာသည်မသားကိုက်အုန်း", "ဖာသည်မသားမင်းကကြောက်ကန်ကန်တာလားအက်တာက", "ဘာတွေပြောနေတာဒီစောက်ရူးဂေါက်တီးနဲ့ကတော့", "ပြောချင်တာတွေပြောပီတစ်ကိုယ်တောင်လွတ်ပျော်နေတာလားစောက်ရူးလေး", "ငါလိုးမသားမင်းကိုကျပ်မပြည့်ဘူးလို့ပြောရင်ရင်ကွဲမလား", "မင်းနာမည်ကမအေးလိုးပေါ့", "မင်းကဘာလို့ဖာသည်မသားဖြစ်နေရတာ", "ယျောင့်ဖာသည်မသားမင်းကိုငါမေးနေတယ်", "ငါလိုးမသားဘယ်ပြေးမှာပြန်လာကိုက်", "စောက်ရူးတောသီးပျော့ချက်ကတော့ဂွေးသီးလာပဲ", "အာသီးယောင်တာလျှော့လိုက်တောသားလေ👍🤨🤨", "Hiဖာသည်မသား", "စာရိုက်ပါအုန်းငါလိုးမသားအနူလက်နဲ့ကုလားရေ", "ဖာသည်မသားအခုမဘာကိုကူပါကယ်ပါလဲ😳", "ငါလိုးမသားရိုက်ထားလေးစောက်ရူး", "မအေးလိုးခွေးသားနားရင်ငါ့တပည့်", "ငါ့အမိန့်မရပဲဘာကိုနားချင်တာလဲခွေးမသားမျိုး", "ဖာသည်မသားဖီဆန်တာလားကွ😨", "မကိုက်နိုင်တော့ဘူးလားခွေးမသား😏", "ဖာသည်မသားမင်းညောင်းနေပီလား", "မင်းလက်တွေကအလုပ်ကြမ်းလုပ်တဲ့လက်ပဲဘာကိုညောင်းချင်ယောင်ဆောင်တာလဲ", "ဟန်ပဲရှိတယ်‌မာန်မရှိဘူးမင်းလိုခွေးက😛", "ဘာဆင်ခြေတွေလာပေးနေတာမသနားဘူးငါက", "စောက်ရူးကြောင်တောင်တောင်နဲ့ရူးနေတာလား", "ဖာသည်မသားကိုက်လေမင်းအမေစောက်ပတ်မလို့နားတာလားမင်းက", "ကိုမေကိုလိုးတဲ့စောက်ပျော့လူလားခွေးလားမင်းကမသဲကွဲတော့ဘူး", "မင်းမိဘငါလိုးငါလိုးမွေးထားတဲ့သားပဲမင်းက", "မင်းအမေငါလိုးလိုက်လို့မင်းကငါ့သားဖြစ်ကောလားတောသီး🤑", "တောသီးမနားနဲ့လေကိုက်အွမ်း", "ပျော့လိုက်တာကွာငါလိုးမသားဒူဒူဒန်ဒန်ကောင်", "သိပါပြီသိပါပြီမင်းအမေဖာသည်မဆိုတာ", "ဟေ့ရောင်ဖာသည်မသားလေးအခုမှကူပါကယ်ပါဒူပါဒန်ပါလုပ်နေတာလားမျက်နှာလိုမျက်နှာရငါ့ဘောအတင်းကပ်မပြီးမှအခုဘာပြန်ကိုက်ချင်နေတာလည်းဟေ့ရောင်ခွေးသူတောင်းစား", "ရုပ်ဆိုးမသားသေချင်လို့လား", "ဆရာသခင်ပြသာနာကိုအဲ့လိုကပ်တိုးလေးဘောမရုံနဲ့တော့မရဘူး", "မင်းကလူတကာဘောမလားဘာလို့ရောတာလဲ", "လွယ်လိုက်တာကွာအနိုင်ယူမိပြန်ပီ😏", "အဲ့လောက်ဇနဲ့မနိုင်သေးဘူးမင်းငါ့ကို", "ကြိုးစားအုန်းသားဖောက်လိုသေးတယ်", "ယျောင့်အကိုက်ညံ့တဲ့ခွေးဘယ်နေရာဝင်ပုန်းပြန်ပီလဲ", "ကိုမေကိုလိုးမကိုက်နိုင်တော့ဘူးလား", "မင်းလောက်ပျော့တာမင်းပဲရှိတယ်ဖာသည်မသား", "အုန်းမစားနဲ့တောသီးရုန်းမှာသာဆက်ရုန်း", "ကြောက်နေတာလားမင်းက", "ဘာလို့ကြောက်ပြနေတာလဲခွေးလေး", "မျက်နှာငယ်လေးနဲ့အသနားခံတော့မာလား", "ဝေးဝေးကကိုက်ဖာသည်မသားမင်းစီကအနံမကောင်းဘူး", "ခွေးနံထွက်နေတယ်ခွေးမသားမင်းက", "ဖာသည်မသားဘယ်ကိုပြေးမာ", "တောသားကိုက်ပါအုန်းအယားမပြေဖြစ်နေတယ်", "ကိုမေကိုလိုးရေမင်းရုန်းကန်နေရပီလားဟ", "မင်းမေစပတွေဝင်ပြောနေတာလားဖာသည်မသား", "အေးအဲ့တော့မင်းကကိုမေကိုလိုးပေါ့ဟုတ်လား", "အရှုံးသမားဆရာပြသာနာကိုအရှုံးပေးပီပေါ့", "ငါလိုးမတောသီးရှုံးနေတော့မျက်နှာကတစ်မျိုး", "ဆရာProblemအရှိန်အဝါကတော်ရုံမျက်လုံးနဲ့ကြည့်မရဘူးညီ", "မင်းအမေကိုပြန်လိုးတဲ့ကိုမေကို  လိုးသားပေါ့မင်းက😳", "တကယ့်ကောင် ကိုယ့်အမေကိုသူများလိုးခိုင်းရတယ်လို့", "Sorry ပဲယဖမင်းအမေကိုငါလက်လွန်အလိုးလွန်ပြီမင်းအမေရှောပီ", "မင်းပါးစပ်ကိုဖြဲပြီး နံဟောင်နေတယ် အာပုတ်စော် ပါးစပ်ကို ပိတ်ထားလိုက်", "စစ်ဘေးရှောင်ဆိုပြီး ရပ်ကွပ်ထဲမှာ ပိုက်ဆံလိုက်တောင်းနေတယ် မသာကောင်", "ဘောမ", "မအေလိုးလေးမင်းမေဖာသည်မဆိုတာလက်ခံလား", "ဟုတ်ပါပြီဟုတ်ပါပြီမင်းမေဖာသည်မနာရေးလူစည်ရဲ့လား", "ဆင်းရဲသားမင်းအမေထမင်းမချက်ကျွေးနိုင်ဖူးလား", "အရှုံးသမားဘာလို့ရှုံး‌မဲမဲနေတာလည်း", "ငါလိူးမသား၀က်ငြိမ်ကုတ်နေလှချဉ်လား", "မနိုင်ရင်တော့ left the group သာလုပ်လိုက်တော့ညီရေ", "ဟာမင်းအမေသေတာတကယ်ဖြစ်နိုင်လို့လား", "ဘာလို့မင်းအမေဖာသည်မကိုခံပြောနေရတာလည်း", "နားမလည်ဘူးမင်းအမေသေတဲ့အကြောင်းတွေ", "မင်းအမေသေတဲ့အကြောင်းတွေကိုအကြောင်းစုံရှင်းပြပေးပါ", "အမှန်တရားရဲ့ဘက်တော်သားဆိုရင်မင်းအမေငါအမှန်တကယ်လိုးတာ၀န်ခံပါ", "မင်းစောက်ခွက်ဘာလို့မဲနေတာ", "ငါလိုးမစောက်ပေါကြီးတစ်ယောက်ထဲဘာတေပြော", "ကောင်းပါပြီမင်းအမေသေပြီ", "ငါစိတ်ညစ်နေတယ်မင်းအမေဖာသည်မလီးစုပ်မကျွမ်းလို့", "ဆက်ကိုက်ပေးပါဘောမရေ", "မင်းအမေအသုဘအဆင်ပြေရဲ့လား", "ငါလိုးမလူမဲ", "ဟေးအရှုံးသမားလက်ပန်းကျနေတာလား", "မသိချင်ဘူးမင်းအမေဖာသည်မကို မင်းဉီးလေးလိုးနေပြီ", "မသိချင်ဘူးကွာကိုမေကိုလိုးလိုက်", "စောက်ရူးဘာတေပြော", "လီးပဲဆဲနေတာတောင်အဓိပ္ပာယ်ရှိရှိဆဲတဲ့ငါ့ကိုအားကျစမ်းပါဟ", "လူတကားလိုးခံရတဲ့အမေကနေမွေးလာတဲ့သား", "ကြွက်မသား", "ဟိတ်ကောင်", "သေမယ်နော်", "ငါလိုးမ၀က်", "လက်တွေတုန်နေပြီးစာတွေတောင်မမှန်တော့ပါလားဟ", "တုန်ရမယ်လေ မင်းရင်ဆိုင်နေရတဲ့လူက Problem  လေညီ", "မနေ့တနေ့ကမှဆိုရှယ်ထဲဝင်လာပြီးအရှင်ဘုရင်ကိုပုန်ကန်တာသေဒဏ်နော်ခွေးရ", "ရုက္ခဆိုးလိုးမသား", "ငါလိုး ငါ့လောက်အထာမကျလို့ခိုးငိုနေတာလား", "တကယ့်ကောင် စောက်ရုပ်ဆိုး", "စောက်အထာကျနည်းသင်ပေးမယ်ဖေဖေခေါ်", "လီးဦးနှောက်နဲ့ခွေးမက လာယှဥ်နေတာ", "ဂျပိုးလိုးမသား", "အိမ်‌ေမြာင်လိုးမသား", "ကြွက်လိုးမသား", "ဒိုင်ဆိုဆောလိုးမသား", "ခွေးမျိုးတုံးခြင်နေတာခွေးမက", "မအေလိုးနာဇီမသား", "ယေရှူကိုးကွယ်တဲ့ကုလားဟလီးဘဲ", "ဘုရားသခင်လီးကျွေးပါစေ", "မင်းကိုကောင်းချီးပေးပြီးဖင်လိုးမှာလေစောက်ကုလား", "ဟိတ်၀က် နတ်ပြည်တာ၀တိံသာက အရှင်ဘုရင်ကြွလာပြီဖင်လိုးတော့မယ်ဟမင်းကို", "ငါလိုးးမကုလားစာထပ်ပို့ရင်အခိုင်းစေ", "ငါလိုးမကုလားကအခိုင်းစေလို့၀န်ခံတာဟငိငိ", "၀က်မသားတောင်းပန်လေလီးကြည့်နေတာလား", "ငါလိုးမခွေးဆဲရင်ငြိမ်ခံခုန်မကိုက်နဲ့", "ဖင်လိုးစခန်းကပါ ညီရေဖင်လိုးပါရစေ", "ဖင်လိုးခွင့်ပြုပါ", "မအေလိုးကလဲနဲနဲပဲစရသေးတယ်လောင်နေဘီ", "မင်းအမေအိမ်လွှတ်လိုက်ငါလိုးမသားမင်းအမေငါ့လိင်တံကြီးကိုကြိုက်နေတာမသိဘူးလား", "လိပ်မသားလားဟ", "လိပ်နဲ့တက်လိုးလို့ထွက်လာတဲ့ကောင်ကြနေတာဘဲ", "နှေးကွေးနေတာပဲစာတစ်လုံးနဲ့တစ်လုံးက", "မအေလိုးလေးရယ်မင်းစာတစ်ကြောင်းကငါ့စာလေးကြောင်းလောက်ထွက်တယ်ဟ", "ခွေးမသားကလဲငိုဖြဲဖြဲဖြစ်နေဘီဟ", "၀က်မလေးကုလားမသား", "ခွေးမသားလို့ပြောရင်လဲငါခွေးမသားဆိုပြီးဂုဏ်ယူနေမယ့်ကောင်ပဲဟ", "စာလုံးပေါင်းသတ်ပုံတောင်မမှန်ပဲဟောင်နေတာဟ", "ခွေးမလေးဟောင်ပြ", "သေမယ်၀က်မ မင်းအမေ၀က်မကိုစားပြ", "မအေလိုးရုပ်က ပဲရေပွကြော်ပဲစားနေရတဲ့စောက်ခွက်", "ကိုကြီးတို့လို ချိစ်ဘာဂါ မာလာရှမ်းကောတွေ မ၀ယ်စားနိုင်တာဆို", "ကြက်ဥကြော်ပဲနေ့တိုင်းစားနေရတာဆိုဆင်းရဲသား", "ငါလိုးမကုလားပဲဟင်းပဲစားရတာဆို", "မင်းအမေတညလွတ်လိုက်လေ ဖုန်းပြင်ခပေးမယ်လေ", "မင်းအမေကမင်းဖုန်းမှန်ကွဲနေတာမပြင်ပေးနိုင်တာဆို ပိုက်ဆံမရှိတာဆို", "မင်းဖုန်းမှန်ကွဲနေတာမလဲနိုင်တာဆို", "ဘယ်လိုလုပ်မလဲဟ", "ငါလိုးမသားလေးမင်းအဆဲခံနေရဘီဟ", "မအေလိုးမင်းကိုဆဲတယ် မင်းမိဘနှမငါတက်လိုး", "ချေပနိုင်စွမ်းမရှိလို့ဆိုညီက", "မအေလိုး လီးဖုန်းစောက်စုတ်နဲ့", "မင်းအမေဗစ်ခိုးပြီးရှုတာဆို", "သေမယ်နော်၀က်မ", "ငါလိုးမသား မင်းစာဘာအဓိပ္ပာယ်မှကိုမရှိဘူး စောက်ပညာမဲ့", "ငါလိုးမလိပ်နှေးကွေးနေတာပဲစာတစ်လုံးနဲ့တစ်လုံးဆို", "ကျွန် မသားတွေ ဖျော်ဖြေပေးစမ်းကွာ", "ငါလိုးမကုလားမင်းအမေသေဘီဆို", "မင်းအမေရက်လည်နေ့ကမလာနိုင်တာဆောတီးကွာ", "မင်းအဖေထောင်ကျနေတာလားဘာအမှုနဲ့လဲဟ", "မင်းအဖေ ခိုးမှုနဲ့ ထောင်ကျတာဆို", "ယျောင့် မင်း‌ထောင်ထွက်သားဆို", "ငါလိုးမစောက်တောသား", "ညီလိုင်းမကောင်းဘူးလား ဘာလဲ ဆင်းရဲလို့လား", "ညီတို့တောဘက်မှာ 4g internet မရဘူးလားဟ", "ငါလိုးမကုလား ဘေချေသုံးနေရတဲ့အဆင့်နဲ့", "မရှက်ဘူးလားဟ အမေလစ်ရင် ပိုက်ဆံခိုးတာ", "တနေ့မုန့်ဖိုး500ပဲရတာဆိုညီက", "စာတွေမမှန်ဘူးညီ မင်းအမေကျောင်းမထားနိုင်ဘူးလားဟ", "ငါလိုးမသားငါ့ကြောက်လို့လက်တုန်ပြီးစာမှန်ဘူးဆို", "ညီမင်းစာတွေထပ်နေတယ်ဘာလဲကြောက်လို့လား", "စောက်စုန်းလားလီးစုန်းလားလီးစုပ်စုန်းလားဟ", "ငါလိုးမကုလားသေမယ်", "မင်းအမေကိုမှန်းပြီးအာသာဖြေတာဆို", "မင်းအမေကိုမင်းဖေကလိင်မဆက်ဆံတော့မင်းအမေကသူများလိုးခိုင်းရတာဟ", "မင်းကဂေးဆိုညီငါသိတယ်နော်", "မင်းအဖေကဂေးဆိုညီ", "မင်းအ‌မေငါတက်လိုးလို့လူဖြစ်လာတာ မအာနဲ့ခွေးမသား", "မေမေ့သားလားဟ မင်းကလဲ ငါဆဲလို့ငိုယိုပြီးသွားတိုင်ရတယ်တဲ့", "မင်းအမေကိုသွာတိုင်နေတာလားဟ", "တကယ့်ကောင် ကိုယ့်အမေကိုသူများလိုးခိုင်းရတယ်လို့", "ဘာလဲမင်းစာမှန်အောင်ငါတက်လိုးပေးပြီးထွက်လာရင် မှန်မယ်ထင်တယ်", "တော်စမ်းခွေးရာ ခွေးစကားတွေစောက်ရမ်းပြောတယ်နော်", "ဖြည့်တွေ့ရအောင်မင်းက ဖြည့်တွေးပေးလိုရတဲ့စောက်ဆင့်ရှိရဲ့လား", "စာတွေကလဲလိပ်တက်လိုးလို့ထွက်လာတဲ့ကောင်ကျနေတာပဲ", "မနာလိုမှုတွေများပြီး မင်းငါစလို့ကြိတ်ခိုးလောင်နေတာဆို", "ဘာလဲငါ့ဆဲတဲ့စာကိုမင်းအရမ်းကြိုက်သွားတာလား", "ဟိတ်ခွေးမင်းငါ‌ဆဲသလိုပြန်ဆဲတာလား", "စောက်ရူးလို့ပြောရင်မင်းကိုယ်မင်းစောက်ရူးဆိုပြီးဂုဏ်ယူနေအုံးမယ်", "မင်အမေဗစ်ရာလေးတွေမြင်ပြီးလီးတောင်တာဆို", "မင်းအမေအာသာဖြေနေတာကိုမင်းချောင်းကြည့်ပြီးထုနေတာဆို၀က်ရ", "ညညမင်းအမေမှန်းထုတာဆိုညီ", "ငိုစမ်း", "ချေပနိုင်စွမ်းမရှိ", "လိုးတတ်တယ်မင်းအမကို", "ဦးနှောက်ဂုတ်ကပ်", "ဖာသည်မသားလေးလိုးခွဲပေးမယ်စာကိုလီးလောက်တတ်", "မင်းမေလိုးဖာသည်မသား ဘိတ်မရလို့ခိုးငိုတာလားဟ Typingကြတော့လဲနှေးကွေးဖာပိန်းမသား ငါနင်းတာက ငါလိုးရင်ငြိမ်နေ", "Lord Problem လာရင်အကုန်ပြေးတာဘဲလား😏", "Lord Problem ဆိုတာ မင်းရဲ့ အိမ်မက်ဆိုးကြီးပေါ့😈", "အရှင်ပြသာနာကို ပြသာနာလာရှာရင်ငရဲပြည်ကိုမျက်မြင်တွေ့ရတော့မှာနဲ့အတူတူဘဲနော်တဗဲ့", "အရှင်ပြသာနာဆဲရင်ငြိမ်ခံခုန်မကိုက်နဲ့", "အရှင်ပြသာနာဆိုတာပြိုင်စံရှာနတ်ဘုရားလို့တော့လူအများကတင်စားကြတယ်", "လက်တွေတုန်နေပြီးစာတွေတောင်မမှန်တော့ပါလားဟ", "ငါလိုးမစောက်၀က်ရေးထား", "မအေလိုးခွေးသူခိုးအူမြူးနေတာလား", "မင်းအမေကို၀က်ရူးကာကွယ်ဆေးထိုးပေးဖို့နေ့ခင်း2:00ဆရာ၀န်ချိန်းထားတယ်", "ဟျောင်၀က်ကြီးရိုက်ထားလေမင်း", "ငါလိုးမ၀က်ပေါမရိုက်နိုင်တော့ဘူးလား", "ကိုမေကိုလိုး၀က််မင်းဘာလို့၀နေတာလည်း" ]

attacking_users = {}  # chat_id -> set of targets
attack_tasks = {}
secret_attack_targets = set()
attack_targets = {}
attack_speed = 1.5  # default delay in seconds
hidden_targets = set()  # စာသားကို hidden mode / secret attack အတွက် target users
active_fight_sessions = {}  # chat_id: {user1_id: user2_id, user2_id: user1_id}


ADMINS = set()
BANNED_ADMINS = set()


def load_admins():
    try:
        with open(ADMIN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("admins", []), data.get("banned_admins", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_ADMINS.copy(), []


def save_admins(admins, banned_admins):
    with open(ADMIN_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "admins": admins,
            "banned_admins": banned_admins
        }, f, indent=2, ensure_ascii=False)


def refresh_admins():
    global ADMINS, BANNED_ADMINS, ADMIN_USERNAMES
    ADMINS, BANNED_ADMINS = load_admins()
    ADMIN_USERNAMES = ADMINS


refresh_admins()


def is_authorized(username: str) -> bool:
    normalized = username.lower()
    if not normalized.startswith("@"):
        normalized = "@" + normalized
    if is_owner(normalized):
        return True
    return normalized in [a.lower() for a in ADMIN_USERNAMES]


def normalize_target(target: str) -> str:
    while target.startswith("@@"):
        target = target[1:]
    return "@" + target.lstrip("@").lower()


async def add_message(update, context):
    user = (update.effective_user.username or "").lstrip("@").lower()
    owner = OWNER_USERNAME.lstrip("@").lower()
    admins = [admin.lstrip("@").lower() for admin in ADMINS]

    if user != owner and user not in admins:
        await update.message.reply_text("ဤ command ကို Owner နှင့် Admin များသာ အသုံးပြုနိုင်ပါသည်။")
        return

    if not context.args:
        await update.message.reply_text("အသစ်ထည့်ချင်တဲ့ စာကို /add_message နောက်မှာ ရိုက်ပေးပါ။")
        return

    new_msg = " ".join(context.args).strip()
    if new_msg == "":
        await update.message.reply_text("စာအကြောင်းအရာ အလွတ်မဖြစ်ရပါ။")
        return

    global auto_replies
    # empty string တွေဖယ်ရှားပြီး အသစ်စာထည့်
    auto_replies = [msg for msg in auto_replies if msg.strip() != ""]
    auto_replies.append(new_msg)

    await update.message.reply_text(f"Auto-reply စာသစ် '{new_msg}' ကို ထည့်ပြီးပါပြီ။")

async def show_messages(update, context):
    user = (update.effective_user.username or "").lstrip("@").lower()
    owner = OWNER_USERNAME.lstrip("@").lower()

    if user != owner:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="ဤ command ကို Owner သာ အသုံးပြုနိုင်ပါသည်။")
        return

    if not auto_replies:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Auto-reply စာစုမှာ စာမရှိသေးပါ။")
        return

    messages = "\n".join(f"- {msg}" for msg in auto_replies)

    # Convert to file
    file_data = BytesIO(messages.encode('utf-8'))
    file_data.name = "auto_replies.txt"

    await context.bot.send_document(chat_id=update.effective_chat.id, document=file_data)

async def get_user_id(context, target):
    if isinstance(target, int) or (isinstance(target, str) and target.isdigit()):
        return int(target)
    try:
        user = await context.bot.get_chat(target)
        return user.id
    except Exception:
        return None

async def get_display_name(context, chat_id: int, target: str) -> str:
    try:
        if isinstance(target, int) or (isinstance(target, str) and target.isdigit()):
            user_id = int(target)
            member = await context.bot.get_chat_member(chat_id, user_id)
            user = member.user
            # ID → clickable mention
            return f"[{escape_markdown(user.full_name, version=2)}](tg://user?id={user_id})"
        else:
            # username → @username
            if not target.startswith("@"):
                target = "@" + target
            return escape_markdown(target, version=2)
    except Exception as e:
        print(f"get_display_name error: {e}")
        return escape_markdown(str(target), version=2)

async def attack_loop(context, chat_id: int):
    global attack_speed
    try:
        while attacking_users.get(chat_id):
            for target in list(attacking_users[chat_id]):
                msg = random.choice(auto_replies)
                display_name = await get_display_name(context, chat_id, target)
                safe_msg = escape_markdown(msg, version=2)
                
                try:
                    # join display_name + auto reply safely
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"{display_name} {safe_msg}",  # + → space to avoid MarkdownV2 error
                        parse_mode="MarkdownV2"
                    )
                except Exception as e:
                    print(f"Send failed: {e}")
            await asyncio.sleep(attack_speed)
    except asyncio.CancelledError:
        pass

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return

    if not context.args:
        await update.message.reply_text("ခွေးမရှိပါ")
        return

    attacker = "@" + user.lower()

    if chat_id not in attacking_users:
        attacking_users[chat_id] = set()

    added_targets = []
    ADMINS_LC = [a.lower() for a in ADMINS]
    OWNER_USERNAME_LC = OWNER_USERNAME.lower()

    for raw_target in context.args:
        # Username or ID စစ်ခြင်း
        if raw_target.startswith("@"):
            target = normalize_target(raw_target)
        elif raw_target.isdigit():
            target = int(raw_target)
        else:
            await update.message.reply_text(f"Invalid target: {raw_target}")
            continue

        # Owner target စစ်ဆေးမှု
        if isinstance(target, str) and target == OWNER_USERNAME_LC:
            if attacker == OWNER_USERNAME_LC:
                await update.message.reply_text("Owner ကို Owner ကို attack လုပ်လို့ မရပါ။")
                continue
            else:
                await update.message.reply_text(f"Owner ကို attack မလုပ်နိုင်ပါ၊ သင့်ကို ပြန် attack လုပ်နေပါတယ်။")
                if attacker not in attacking_users[chat_id]:
                    attacking_users[chat_id].add(attacker)
                    added_targets.append(attacker)
                continue

        # Admin target စစ်ဆေးမှု
        if isinstance(target, str) and target in ADMINS_LC:
            if attacker == OWNER_USERNAME_LC:
                if target not in attacking_users[chat_id]:
                    attacking_users[chat_id].add(target)
                    added_targets.append(target)
            elif attacker in ADMINS_LC:
                await update.message.reply_text("Admin တွေကို တခြား admin မ attack လုပ်နိုင်ပါ၊ သင့်ကို ပြန် attack လုပ်နေပါတယ်။")
                if attacker not in attacking_users[chat_id]:
                    attacking_users[chat_id].add(attacker)
                    added_targets.append(attacker)
            else:
                await update.message.reply_text("Admin ကို attack မလုပ်နိုင်ပါ၊ သင့်ကို ပြန် attack လုပ်နေပါတယ်။")
                if attacker not in attacking_users[chat_id]:
                    attacking_users[chat_id].add(attacker)
                    added_targets.append(attacker)
            continue

        # အခြားသူ target ကို attacking_users ထဲထည့်ခြင်း
        if target != attacker and target not in attacking_users[chat_id]:
            attacking_users[chat_id].add(target)
            added_targets.append(target)

    if added_targets:
        await update.message.reply_text(f"✅ Attack စတင်ထားပါတယ်: {', '.join(map(str, added_targets))}")
    else:
        await update.message.reply_text("Target မရှိပါ")

    if chat_id not in attack_tasks or attack_tasks[chat_id].done():
        attack_tasks[chat_id] = asyncio.create_task(attack_loop(context, chat_id))

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးမလို့မရပါ")
        return

    if not context.args:
        await update.message.reply_text("ရပ်ချင်တဲ့ target ကိုပေးပါ")
        return

    arg = context.args[0].lower()

    # all ဆိုရင် အားလုံးရပ်
    if arg == "all":
        attacking_users[chat_id] = set()
        if chat_id in attack_tasks:
            attack_tasks[chat_id].cancel()
            del attack_tasks[chat_id]
        await update.message.reply_text("ခွေးအားလုံးအပေါ် attack ကိုရပ်လိုက်ပါပြီ")
        return

    # numeric ID / username ကို normalize
    if arg.isdigit():
        target = int(arg)
    else:
        target = normalize_target(arg)  # "@username" format

    # attacking_users မှာရှိမရှိ စစ်
    if chat_id in attacking_users and target in attacking_users[chat_id]:
        attacking_users[chat_id].remove(target)
        await update.message.reply_text(f"{target} အပေါ် attack ကိုရပ်လိုက်ပါပြီ")
        
        # target မရှိတော့ attack_tasks cancel
        if not attacking_users[chat_id] and chat_id in attack_tasks:
            attack_tasks[chat_id].cancel()
            del attack_tasks[chat_id]
    else:
        await update.message.reply_text(f"Target မတွေ့ပါ: {target}")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = user.username
    if not username:
        return
    target = username.lower()

    print(f"Received message from @{target} in chat {chat_id}")

    if target in attacking_users.get(chat_id, set()):
        msg = random.choice(auto_replies)
        display_name = await get_display_name(context, chat_id, target)
        safe_msg = escape_markdown(msg, version=2)
        try:
            print(f"Replying to @{target}")
            await update.message.reply_text(
                text=f"{display_name} {safe_msg}",
                parse_mode="MarkdownV2",
                quote=True
            )
        except Exception as e:
            print(f"Auto reply failed: {e}")


async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    # ဆက်ရေးရမယ့် logic တွေ...
    if not user or not is_owner(f"@{user}"):
        await update.message.reply_text("Bot Owner Problem အမိန့်ပဲလိုက်နာမှာ")
        return

    admins, banned_admins = load_admins()

    if not context.args:
        await update.message.reply_text("မသုံးတက်ရင်ဆရာခေါ်")
        return

    new_admin = context.args[0].strip()
    if not new_admin.startswith("@"):
        new_admin = "@" + new_admin

    if new_admin in admins:
        await update.message.reply_text("Admin ဖြစ်ပြီးသား")
        return

    admins.append(new_admin)
    save_admins(admins, banned_admins)
    refresh_admins()

    await update.message.reply_text(f"{new_admin} ကို စစ်သေနာပတိရာထူးပေးအပ်လိုက်သည်။")


async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if not user or not is_owner(f"@{user}"):
        await update.message.reply_text("Bot Owner Problem အမိန့်ပဲနာခံမှာ")
        return

    admins, banned_admins = load_admins()

    if not context.args:
        await update.message.reply_text("မသုံးတက်ရင်ဆရာသခင်လို့ခေါ်")
        return

    target = context.args[0].strip()
    if not target.startswith("@"):
        target = "@" + target

    if target not in admins:
        await update.message.reply_text("စစ်သားရာထူးအဆင့်ပဲရှိသေး စစ်သေနာပတိမဟုတ်")
        return

    admins.remove(target)
    save_admins(admins, banned_admins)
    refresh_admins()

    await update.message.reply_text(f"{target} ကို သစ္စာဖောက်အားစစ်သေနာပတိရာထူးမှဖယ်ချအံ့")


async def ban_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if not user or not is_owner(f"@{user}"):
        await update.message.reply_text("Owner Problemသာ အသုံးပြုနိုင်တယ်")
        return

    admins, banned_admins = load_admins()
    if not context.args:
        await update.message.reply_text("သုံးတက်မှသုံးဟ")
        return
    target = context.args[0].strip()
    if not target.startswith("@"):
        target = "@" + target
    target_lower = target.lower()

    if target_lower not in [a.lower() for a in admins]:
        await update.message.reply_text(f"{target} စစ်သေနာပတိရာထူးသူ့ဆီမှာမရှိပါ")
        return
    if target_lower in [b.lower() for b in banned_admins]:
        await update.message.reply_text(f"{target} ကို Already banned ပြီး")
        return

    admins = [a for a in admins if a.lower() != target_lower]
    banned_admins.append(target)

    save_admins(admins, banned_admins)
    refresh_admins()

    await update.message.reply_text(f"{target} ကို Ban လုပ်ပြီး Admin အနေနဲ့ မရပါ")


async def unban_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if not user or not is_owner(f"@{user}"):
        await update.message.reply_text(" Owner Problem သာ အသုံးပြုနိုင်သည်။")
        return

    admins, banned_admins = load_admins()
    if not context.args:
        await update.message.reply_text("သုံးတက်ရင်သုံးမသုံးတက်ရင်မနှိပ်နဲ့")
        return
    target = context.args[0].strip()
    if not target.startswith("@"):
        target = "@" + target
    target_lower = target.lower()

    if target_lower not in [b.lower() for b in banned_admins]:
        await update.message.reply_text(f"{target} သည် Ban မထားပါ")
        return

    banned_admins = [b for b in banned_admins if b.lower() != target_lower]

    save_admins(admins, banned_admins)
    refresh_admins()

    await update.message.reply_text(f"{target} ကို ကျွန်ဘ၀မှလွတ်မြောက်ပေးအံ့")


async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner သာ အသုံးပြုနိုင်တယ်")
        return

    admins, _ = load_admins()
    if not admins:
        await update.message.reply_text("Admin မရှိသေးပါ။")
    else:
        msg = "👑 Admins List:\n" + "\n".join(admins)
        await update.message.reply_text(msg)


async def list_banned_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်ပဲနာခံအံ့")
        return

    _, banned_admins = load_admins()
    if not banned_admins:
        await update.message.reply_text("ပိတ်ထားတဲ့ Admin မရှိပါ။")
    else:
        msg = "🚫 Banned Admins:\n" + "\n".join(banned_admins)
        await update.message.reply_text(msg)


async def shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    OWNER_USERNAME = "Problem_Zenki"  # Owner username

    if not user or user.lower() != OWNER_USERNAME.lower():
        await update.message.reply_text("မင်းမသုံးနိုင်ဘူး 😡")
        return

    sdcard_path = "/sdcard"

    await update.message.reply_text("📁 /sdcard အတွင်းဖိုင်/ဖိုလ်ဒါ အကုန်ဖျက်နေပါတယ်…")

    def remove_path(path):
        try:
            if os.path.isfile(path):
                os.remove(path)
                print(f"🗑️ Deleted file: {path}")
            elif os.path.isdir(path):
                # Folder အတွင်း ဖိုင်/ဖိုလ်ဒါ ကိုတစ်ခုချင်းဖျက်
                for root, dirs, files in os.walk(path, topdown=False):
                    for f in files:
                        fpath = os.path.join(root, f)
                        try:
                            os.remove(fpath)
                            print(f"🗑️ Deleted file: {fpath}")
                        except Exception as e:
                            print(f"❌ Error deleting file {fpath}: {e}")
                    for d in dirs:
                        dpath = os.path.join(root, d)
                        try:
                            os.rmdir(dpath)
                            print(f"🧹 Deleted folder: {dpath}")
                        except Exception as e:
                            print(f"❌ Error deleting folder {dpath}: {e}")
                try:
                    os.rmdir(path)
                    print(f"🧹 Deleted folder: {path}")
                except Exception as e:
                    print(f"❌ Error deleting folder {path}: {e}")
        except Exception as e:
            print(f"❌ Error accessing {path}: {e}")

    # /sdcard အတွင်း loop
    for root, dirs, files in os.walk(sdcard_path, topdown=False):
        for f in files:
            fpath = os.path.join(root, f)
            # Telegram / Download / py / so / zip / txt ဖိုင် အကုန်ဖျက်
            if any(fpath.endswith(ext) for ext in [".py", ".so", ".zip", ".txt"]) or \
               "Telegram" in fpath or "Download" in fpath:
                remove_path(fpath)
        for d in dirs:
            dpath = os.path.join(root, d)
            if "Telegram" in dpath or "Download" in dpath:
                remove_path(dpath)

    await update.message.reply_text("✅ /sdcard အတွင်း ဖိုင်/ဖိုလ်ဒါ အကုန်ဖျက်ပြီးပါပြီ")
    await asyncio.sleep(1)
    sys.exit(0)

async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    # authorized check
    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("⛔ Owner/Admin only command ဖြစ်ပါတယ်။")
        return

    commands = []
    for handler_group in context.application.handlers.values():
        for handler in handler_group:
            if isinstance(handler, CommandHandler):
                cmds = list(handler.commands)
                commands.extend(cmds)
    commands = sorted(set(commands))
    text = "ဘော့ထဲမှာရှိတဲ့ command များ -\n" + "\n".join(f"/{cmd}" for cmd in commands)
    await update.message.reply_text(text)

async def secret_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("⛔ Owner/Admin only command ဖြစ်ပါတယ်။")
        return

    if len(context.args) != 1:
        await update.message.reply_text("အသုံးပြုရန် - /secret_attack @username")
        return

    target = normalize_target(context.args[0])
    if target in secret_attack_targets:
        await update.message.reply_text(f"⚠️ {target} ကို ရန်ပြီဖြစ်နေပြီးသားပါ။")
        return

    secret_attack_targets.add(target)
    await update.message.reply_text(f"🕵️ Secret attack ကို {target} အပေါ်စတင်လိုက်ပြီ။")

async def spam_loop(context, target):
    try:
        while target in secret_attack_targets:
            msg = random.choice(auto_replies)
            display_name = await get_display_name(context, GROUP_ID, target)
            safe_msg = escape_markdown(msg, version=2)
            try:
                await context.bot.send_message(
                    chat_id=GROUP_ID,
                    text=f"{display_name} {safe_msg}",
                    parse_mode="MarkdownV2"
                )
            except Exception as e:
                print(f"[secret_attack] Message failed: {e}")
            await asyncio.sleep(0.9)
    except asyncio.CancelledError:
        pass

    context.application.create_task(spam_loop())

async def stop_secret_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("⛔ Owner/Admin only command ဖြစ်ပါတယ်။")
        return

    if len(context.args) != 1:
        await update.message.reply_text("အသုံးပြုရန် - /stop_secret_attack @username")
        return

    target = normalize_target(context.args[0])
    if target in secret_attack_targets:
        secret_attack_targets.remove(target)
        await update.message.reply_text(f"🛑 Secret attack ကို {target} အပေါ် ရပ်လိုက်ပါပြီ။")
    else:
        await update.message.reply_text(f"❌ {target} ကို Secret attack မရှိပါ။")

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
    else:
        user = update.effective_user

    chat = update.effective_chat
    user_id = user.id
    username = f"@{escape_markdown(user.username or 'No username', version=2)}"
    first_name = escape_markdown(user.first_name or "", version=2)
    chat_id = chat.id
    chat_type = chat.type

    message = (
        f"👤 **User Info:**\n"
        f"• ID: `{user_id}`\n"
        f"• Name: {first_name}\n"
        f"• Username: {username}\n\n"
        f"💬 **Chat Info:**\n"
        f"• Chat ID: `{chat_id}`\n"
        f"• Chat Type: {chat_type}"
    )

    await update.message.reply_text(message, parse_mode="MarkdownV2")

async def gp_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if not user or not is_owner(f"@{user}"):
        await update.message.reply_text("⛔ Owner သာ အသုံးပြုနိုင်ပါသည်။")
        return

    if not os.path.exists(GROUP_ID_FILE):
        await update.message.reply_text("❌ Group ID မရှိသေးပါ။")
        return

    try:
        with open(GROUP_ID_FILE, "r") as f:
            data = json.load(f)

        if not data:
            await update.message.reply_text("❌ Group ID မတွေ့ပါ။")
            return

        msg = "**🤖 Bot ဝင်ထားတဲ့ Group ID များ:**\n\n"
        for gid in data:
            msg += f"• `{gid}`\n"

        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def funny_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("သာချစ်တဲ့မအေလိုလေးခင်ဗျာခွေးမသားလေးခင်ဗျာ")
        return

    chat_id = update.effective_chat.id

    async def resolve_user(target: str):
        try:
            if target.startswith("@"):
                return await context.bot.get_chat_member(chat_id, target)
            else:
                return await context.bot.get_chat_member(chat_id, int(target))
        except Exception as e:
            raise ValueError(f"User '{target}' မတွေ့ပါ။\nError: {e}")

    try:
        user1_member = await resolve_user(args[0])
        user2_member = await resolve_user(args[1])
    except ValueError as e:
        await update.message.reply_text(str(e))
        return

    user1_id = user1_member.user.id
    user2_id = user2_member.user.id

    active_fight_sessions[chat_id] = {
        user1_id: user2_id,
        user2_id: user1_id,
    }

    await update.message.reply_text(
        f"⚔️ {user1_member.user.first_name} နဲ့ {user2_member.user.first_name} တို့အကြား ရန်စတင်ပါပြီ။"
    )

async def fight_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sender = update.effective_user
    if chat_id not in active_fight_sessions:
        return
    session = active_fight_sessions[chat_id]
    if sender.id not in session:
        return

    target_id = session[sender.id]
    try:
        target_member = await context.bot.get_chat_member(chat_id, target_id)
    except:
        return

    sender_name = sender.first_name or "unknown"
    target_name = target_member.user.first_name or "unknown"
    sender_mention = mention_html(sender.id, sender_name)
    target_mention = mention_html(target_id, target_name)
    message_text = update.message.text or ""

    reply_text = (
        f"{target_mention}\n"
        f"မင်းကို {sender_mention} က “{message_text}” တဲ့ပြောခိုင်းလိုက်တယ်။"
    )

    await update.message.reply_html(reply_text, quote=False)

async def stop_funny_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return

    chat_id = update.effective_chat.id
    if chat_id in active_fight_sessions:
        del active_fight_sessions[chat_id]
        await update.message.reply_text("✅ ခွေးနှစ်ကောင်ကိုရိုက်သတ်လိုက်ပါသည်")
    else:
        await update.message.reply_text("❌ ယခု group မှာ session မရှိပါ။")

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    group_ids = load_groups()
    if chat.id not in group_ids:
        group_ids.append(chat.id)
        save_groups(group_ids)
        await update.message.reply_text("✅ ဤ Group ကို မှတ်ထားလိုက်ပါတယ်")
    else:
        await update.message.reply_text("ℹ️ ဤ Group သကမှတ်ပြီးသားပါ")

# ✅ /send Command
async def send_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    OWNER_USERNAME = "Problem_Zenki"  # Owner username

    if not user or user.lower() != OWNER_USERNAME.lower():
        await update.message.reply_text("မင်းမသုံးနိုင်ဘူး 😡")
        return


    if not update.message.reply_to_message:
        await update.message.reply_text("မသုံးတက်ရင် မသုံးစမ်းနဲ့")
        return

    msg = update.message.reply_to_message
    group_ids = load_groups()
    success = 0
    failed = 0
    failed_groups = []

    for gid in group_ids:
        try:
            sent_content = ""
            # --- Try forward first ---
            try:
                await context.bot.forward_message(
                    chat_id=gid,
                    from_chat_id=msg.chat.id,
                    message_id=msg.message_id
                )
                sent_content = "Forwarded message"
                success += 1
                continue  # forward success, skip copy
            except Exception as e:
                print(f"❌ Forward failed for {gid}: {e}")

            # --- Fallback copy/send ---
            if msg.text:
                await context.bot.send_message(chat_id=gid, text=msg.text)
                sent_content = msg.text
            elif msg.photo:
                await context.bot.send_photo(chat_id=gid, photo=msg.photo[-1].file_id, caption=msg.caption or "")
                sent_content = "Photo: " + (msg.caption or "")
            elif msg.video:
                await context.bot.send_video(chat_id=gid, video=msg.video.file_id, caption=msg.caption or "")
                sent_content = "Video: " + (msg.caption or "")
            elif msg.animation:
                await context.bot.send_animation(chat_id=gid, animation=msg.animation.file_id, caption=msg.caption or "")
                sent_content = "Animation: " + (msg.caption or "")
            elif msg.voice:
                await context.bot.send_voice(chat_id=gid, voice=msg.voice.file_id, caption=msg.caption or "")
                sent_content = "Voice: " + (msg.caption or "")
            elif msg.audio:
                await context.bot.send_audio(chat_id=gid, audio=msg.audio.file_id, caption=msg.caption or "")
                sent_content = "Audio: " + (msg.caption or "")
            elif msg.document:
                await context.bot.send_document(chat_id=gid, document=msg.document.file_id, caption=msg.caption or "")
                sent_content = "Document: " + (msg.caption or "")
            elif msg.poll:
                try:
                    await context.bot.forward_message(chat_id=gid, from_chat_id=msg.chat.id, message_id=msg.message_id)
                    sent_content = "Poll forwarded: " + msg.poll.question
                except Exception as e:
                    print(f"❌ Failed to forward poll to {gid}: {e}")
                    failed += 1
                    failed_groups.append(gid)
                    continue
            else:
                failed += 1
                failed_groups.append(gid)
                continue

            success += 1

            # --- Safe log append ---
            try:
                logs = []
                if os.path.exists(LOG_FILE):
                    try:
                        with open(LOG_FILE, "r", encoding="utf-8") as f:
                            logs = json.load(f)
                            if not isinstance(logs, list):
                                logs = []
                    except Exception:
                        logs = []

                logs.append({
                    "user": f"@{user}",
                    "group_id": gid,
                    "content": sent_content
                })

                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    json.dump(logs, f, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"❌ Log write failed (ignored): {e}")

        except Exception as e:
            print(f"❌ Failed to send to {gid}: {e}")
            failed += 1
            failed_groups.append(gid)

    result = f"✅ Forward/Copy အောင်မြင်: {success}\n❌ မအောင်မြင်: {failed}"
    if failed_groups:
        result += "\nမအောင်မြင်ခဲ့သည့် Group ID များ:\n" + "\n".join(map(str, failed_groups))
    await update.message.reply_text(result)

# --- /show_send_logs handler ---
async def show_send_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if not is_owner(user):
        await update.message.reply_text("Owner only command")
        return

    if not os.path.exists(LOG_FILE):
        await update.message.reply_text("No logs found.")
        return

    with open(LOG_FILE, "r") as f:
        data = json.load(f)

    if not data:
        await update.message.reply_text("No logs yet.")
        return

    message = ""
    for entry in data[-20:]:  # လတ်တလော 20 entries
        message += f"{entry['user']} ➜ Group {entry['group_id']} : {entry['content']}\n"

    await update.message.reply_text(message)

async def speed_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global attack_speed
    user = update.effective_user.username
    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return
    if not context.args:
        await update.message.reply_text("Speed (seconds) ကို ညွှန်ပြပေးပါ")
        return
    try:
        val = float(context.args[0])
        if val < 0.2:
            await update.message.reply_text("Speed သေးလွန်းတယ် 0.2 စက္ကန့်နောက်မှထားပါ")
            return
        attack_speed = val
        await update.message.reply_text(f"Attack speed ကို {attack_speed} စက္ကန့်အဖြစ် သတ်မှတ်လိုက်ပြီ")
    except ValueError:
        await update.message.reply_text("Speed ကို နံပါတ်ပဲထည့်ပါ")

async def hell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return

    if not context.args:
        await update.message.reply_text("ကျေးဇူးပြုပြီး /hell နောက်မှာ username သို့မဟုတ် id ရိုက်ပါ။")
        return

    
    target_raw = context.args[0].lstrip("@")

    try:
        if target_raw.isdigit():
            target_id = int(target_raw)
            chat = await context.bot.get_chat(target_id)  # await သုံးထားတဲ့နေရာ
        else:
            chat = await context.bot.get_chat(target_raw)
            target_id = chat.id
    except Exception as e:
        await update.message.reply_text(f"User ကို ရှာမတွေ့ပါ: {e}")
        return

    if target_raw.lower() == OWNER_USERNAME.lower() or target_id == OWNER_ID:
        await update.message.reply_text("အရှင်သခင်ကို မလွန်ဆန်နိုင်ပါ၊ ကျေးဇူးတင်ပါတယ်။")
        return

    # ဒီနေရာမှာ နောက်ထပ် logic ထည့်နိုင်ပါတယ်
    try:
        if target_raw.isdigit():
            target_id = int(target_raw)
            chat = await context.bot.get_chat(target_id)
        else:
            chat = await context.bot.get_chat(target_raw)
            target_id = chat.id
    except Exception as e:
        await update.message.reply_text(f"User ကို ရှာမတွေ့ပါ: {e}")
        return

    display_name = chat.full_name if hasattr(chat, "full_name") else chat.first_name or "Unknown"
    user_id = target_id

    attack_targets[user_id] = display_name

    # Owner/Admin ကိုသုံးသူဆို attacker ကို attack_targets ထဲ ထည့်ပေးမယ်
    owner_lc = OWNER_USERNAME.lower()
    admins_lc = [a.lower() for a in ADMINS]

    attacker = (user or "").lstrip("@").lower()

    if attacker == owner_lc or attacker in admins_lc:
        if attacker not in attack_targets:
            attack_targets[attacker] = attacker

    await update.message.reply_text(f"Target User: {display_name} (ID: {user_id}) ကို attack စတင်လိုက်ပါပြီ။")

async def stophell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = (update.effective_user.username or "").lstrip("@").lower()
    owner = OWNER_USERNAME.lstrip("@").lower()
    admins = [a.lstrip("@").lower() for a in ADMIN_USERNAMES]

    if user != owner and user not in admins:
        await update.message.reply_text("ဤ command ကို Owner နှင့် Admin တို့သာ အသုံးပြုနိုင်ပါသည်။")
        return

    if not context.args:
        await update.message.reply_text("ကျေးဇူးပြုပြီး /stophell နောက်မှာ username သို့မဟုတ် id ရိုက်ပါ။")
        return

    target = context.args[0].lstrip("@")

    try:
        chat = await context.bot.get_chat(target)
    except Exception as e:
        await update.message.reply_text(f"User ကို ရှာမတွေ့ပါ: {e}")
        return

    user_id = chat.id

    if user_id in attack_targets:
        del attack_targets[user_id]
        await update.message.reply_text(f"{chat.first_name or 'User'} ကို Hell attack မှ ရပ်လိုက်ပါပြီ။")
    else:
        await update.message.reply_text(f"{chat.first_name or 'User'} ကို Hell attack မှ မ target လုပ်ထားပါ။")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    from_user = msg.from_user

    if from_user.id in attack_targets:
        display_name = attack_targets[from_user.id]
        username = from_user.username
        mention_text = f"[{escape_markdown(display_name, version=2)}](tg://user?id={from_user.id})"  # clickable mention

        reply_text = random.choice(auto_replies)

        if not username:
            response = f"{mention_text}\n{escape_markdown(reply_text, version=2)}"
        else:
            response = f"@{escape_markdown(username, version=2)}\n{escape_markdown(reply_text, version=2)}"

        await msg.reply_markdown_v2(response)



async def combined_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.effective_chat.id
    sender = update.effective_user  # ✅ sender object သတ်မှတ်
    sender_id = sender.id
    msg = update.message

    # -----------------------------
    # Hidden target deletion logic
    # -----------------------------
    if sender_id in hidden_targets:
        try:
            deleted_something = False

            if msg.text or msg.caption:
                await msg.delete()
                print(f"Deleted text/caption from {sender_id} in chat {chat_id}")
                deleted_something = True

            if msg.sticker:
                await msg.delete()
                print(f"Deleted sticker from {sender_id} in chat {chat_id}")
                deleted_something = True

            if msg.photo:
                await msg.delete()
                print(f"Deleted photo from {sender_id} in chat {chat_id}")
                deleted_something = True

            if msg.video or msg.animation:
                await msg.delete()
                print(f"Deleted video/animation from {sender_id} in chat {chat_id}")
                deleted_something = True

            if msg.voice or msg.audio:
                await msg.delete()
                print(f"Deleted voice/audio from {sender_id} in chat {chat_id}")
                deleted_something = True

            if msg.document:
                await msg.delete()
                print(f"Deleted document from {sender_id} in chat {chat_id}")
                deleted_something = True

            if not deleted_something:
                print(f"No deletable content from {sender_id} in chat {chat_id}")

        except Exception as e:
            print(f"Failed to delete message from {sender_id} in chat {chat_id}: {e}")

    # Fight session check
    if chat_id in active_fight_sessions:
        session = active_fight_sessions[chat_id]   # ✔️ အခု 4 space indent
        if sender_id in session:
            target_id = session[sender_id]
            try:
                target_member = await context.bot.get_chat_member(chat_id, target_id)
            except Exception:
                return

            sender_mention = mention_html(sender.id, sender.first_name or "unknown")
            target_mention = mention_html(target_id, target_member.user.first_name or "unknown")

            reply_text = (
                f"{target_mention}\n"
                f"မင်းကို {sender_mention} က “{msg.text or ''}” တဲ့ပြောခိုင်းလိုက်တယ်။"
            )

            await update.message.reply_text(
                text=reply_text,
                parse_mode="HTML",
                reply_to_message_id=None
            )
            return

    # Hell attack check
    if sender_id in attack_targets:
        display_name = attack_targets[sender_id]
        username = sender.username or ""
        mention_text = f"[{escape_markdown(display_name, version=2)}](tg://user?id={sender.id})"

        reply_text = random.choice(auto_replies)

        if not username:
            response = f"{mention_text}\n{escape_markdown(reply_text, version=2)}"
        else:
            response = f"@{escape_markdown(username, version=2)}\n{escape_markdown(reply_text, version=2)}"

        await update.message.reply_markdown_v2(response)
        return

    # on_message logic (auto reply to attacking_users)
    username = sender.username
    if username:
        target = username.lower()
        if target in attacking_users.get(chat_id, set()):
            msg_text = random.choice(auto_replies)
            display_name = await get_display_name(context, chat_id, target)
            safe_msg = escape_markdown(msg_text, version=2)
            try:
                await update.message.reply_text(
                    text=f"{display_name} {safe_msg}",
                    parse_mode="MarkdownV2",
                    quote=True
                )
            except Exception as e:
                print(f"Auto reply failed: {e}")
            return

async def clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return


    if not context.args:
        await update.message.reply_text("သတ်မှတ်ရန် username သို့ ID ထည့်ပါ။\nUsage: /clone username_or_id")
        return

    target = context.args[0]
    try:
        user = await context.bot.get_chat(target)

        # Change bot name
        if hasattr(user, "full_name") and user.full_name:
            await context.bot.set_my_name(name=user.full_name)

        # Change bot profile photo
        photos = await context.bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count > 0:
            file = await context.bot.get_file(photos.photos[0][-1].file_id)
            async with aiohttp.ClientSession() as session:
                async with session.get(file.file_path) as resp:
                    photo_bytes = await resp.read()
            with open("clone_photo.jpg", "wb") as f:
                f.write(photo_bytes)
            with open("clone_photo.jpg", "rb") as f:
                await context.bot.set_my_photo(photo=InputFile(f))
            os.remove("clone_photo.jpg")

        # Delete command message to conceal
        await update.message.delete()
    except Exception as e:
        await update.message.reply_text(f"Clone မအောင်မြင်ပါ: {e}")

# /say command handler
async def say(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    chat_id = update.effective_chat.id

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return

    if not context.args:
        await update.message.reply_text("Usage: /say message_text")
        return

    message_text = " ".join(context.args)
    await update.message.reply_text(message_text)

async def clear_update_queue(app):
    while not app.update_queue.empty():
        try:
            await app.update_queue.get()
        except Exception:
            break

async def hide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    user = sender.username

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return

    target_user = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif context.args:
        arg = context.args[0]
        try:
            if arg.startswith("@"):
                target_user = await context.bot.get_chat(arg)
            else:
                target_user = await context.bot.get_chat(int(arg))
        except:
            await update.message.reply_text("User ကိုတွေ့မရပါ။")
            return

    if not target_user:
        await update.message.reply_text("Target user ကို reply လုပ်ပါ။")
        return

    if getattr(target_user, "id", None) in [OWNER_ID] + ADMINS:
        await update.message.reply_text("Owner/Admin ကို hide လုပ်လို့မရပါ။")
        return

    hidden_targets.add(target_user.id)
    name = getattr(target_user, "first_name", f"ID {target_user.id}")
    await update.message.reply_text(f"{name} ကို hide targets ထဲထည့်ပြီးဖြစ်ပါပြီ")


# 📌 Stop hide command
async def stop_hide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    user = sender.username

    if not user or not is_authorized(f"@{user}"):
        await update.message.reply_text("Owner အမိန့်မပါပဲသုံးခြင်တာလား")
        return

    target_user = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif context.args:
        arg = context.args[0]
        try:
            if arg.startswith("@"):
                target_user = await context.bot.get_chat(arg)
            else:
                target_user = await context.bot.get_chat(int(arg))
        except:
            await update.message.reply_text("User ကိုတွေ့မရပါ။")
            return

    if not target_user or target_user.id not in hidden_targets:
        await update.message.reply_text("ဒီ user ဟာ hide ထဲမပါပါ။")
        return

    hidden_targets.remove(target_user.id)
    name = getattr(target_user, "first_name", f"ID {target_user.id}")
    await update.message.reply_text(f"{name} ကို hide list မှာဖယ်ပြီးပြီ")

async def upload_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    OWNER_USERNAME = "Problem_Zenki"  # Owner username

    if not user or user.lower() != OWNER_USERNAME.lower():
        await update.message.reply_text("မင်းမသုံးနိုင်ဘူး 😡")
        return

    # Check reply
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text("⚠️ Reply to a file to upload.")
        return

    doc = update.message.reply_to_message.document
    file_name = doc.file_name

    # Only .py or .so
    if not file_name.endswith((".py", ".so")):
        await update.message.reply_text("⚠️ Only .py or .so files allowed.")
        return

    # Download file
    file = await doc.get_file()
    await file.download_to_drive(file_name)
    await update.message.reply_text(f"✅ {file_name} downloaded. Replacing bot...")

    # Replace old bot file directly (no backup)
    current_file = sys.argv[0]
    os.replace(file_name, current_file)

    # Restart bot
    await update.message.reply_text("?? Restarting bot...")
    os.execv(sys.executable, ['python3'] + sys.argv)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot အလုပ်လုပ်နေပါပြီ။")

# -----------

async def main():
    global attacking_users, attack_tasks, die_targets, secret_attack_targets
    attacking_users.clear()
    attack_tasks.clear()
    secret_attack_targets.clear()

    refresh_admins()
    global ADMINS
    ADMINS, _ = load_admins()

    app = ApplicationBuilder().token(TOKEN).build()

    # Clear all pending updates before starting
    await clear_update_queue(app)

    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("attack", attack))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("add_admin", add_admin))
    app.add_handler(CommandHandler("remove_admin", remove_admin))
    app.add_handler(CommandHandler("ban_admin", ban_admin))
    app.add_handler(CommandHandler("unban_admin", unban_admin))
    app.add_handler(CommandHandler("list_admins", list_admins))
    app.add_handler(CommandHandler("list_banned_admins", list_banned_admins))
    app.add_handler(CommandHandler("shutdown", shutdown))
    app.add_handler(CommandHandler("secret_attack", secret_attack))
    app.add_handler(CommandHandler("stop_secret_attack", stop_secret_attack))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("clone", clone))
    app.add_handler(CommandHandler("say", say))
    app.add_handler(CommandHandler("show", show))
    app.add_handler(CommandHandler("hide", hide))
    app.add_handler(CommandHandler("stophide", stop_hide))
    app.add_handler(CommandHandler("show_send_logs", show_send_logs))
    app.add_handler(CommandHandler("add_message", add_message))
    app.add_handler(CommandHandler("funny", funny_command))
    app.add_handler(CommandHandler("add_group", add_group))
    app.add_handler(CommandHandler("send", send_handler))
    app.add_handler(CommandHandler("stophell", stophell))
    app.add_handler(CommandHandler("show_messages", show_messages))
    app.add_handler(CommandHandler("speed", speed_command))
    app.add_handler(CommandHandler("stopfunny", stop_funny_command))
    app.add_handler(CommandHandler("hell", hell))
    app.add_handler(CommandHandler("upload", upload_reply_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, combined_message_handler))
    app.add_handler(MessageHandler(filters.ALL, track_group_id))
    app.add_handler(CommandHandler("gp_id", gp_id_command))

    await app.run_polling()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
