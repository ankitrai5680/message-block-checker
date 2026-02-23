import streamlit as st
import re

# ================= CATEGORY POLICY =================
CATEGORY_POLICY = {
    # BLOCKED
    "DIRECT_PHONE_NUMBER": "BLOCKED",
    "SYMBOL_SEPARATED_PHONE": "BLOCKED",
    "MIXED_WORD_DIGIT_PHONE": "BLOCKED",
    "DOUBLE_TRIPLE_EXPANSION_PHONE": "BLOCKED",
    "COMPACT_REPETITION_PHONE": "BLOCKED",
    "MULTI_EVASION_SINGLE_MESSAGE": "BLOCKED",
    "MULTI_MESSAGE_DIGIT_SPLIT": "BLOCKED",
    "EMAIL_SHARED": "BLOCKED",
    "NON_MAP_LINK_SHARED": "BLOCKED",

    # ALLOWED
    "MAPS_LINK_SHARED": "ALLOWED",
    "PRICE_AMOUNT": "ALLOWED",
    "YEAR_REFERENCE": "ALLOWED",
    "KMS_DISTANCE": "ALLOWED",
    "EMI_OR_FINANCE_CONTEXT": "ALLOWED",
    "GENERIC_NUMBER": "ALLOWED",
    "SAFE_DECIMAL": "ALLOWED",
    "NO_CONTACT_DETECTED": "ALLOWED"
}

# ================= MULTI-LANGUAGE DIGIT NORMALISATION =================
INDIAN_DIGIT_MAPS = [
    str.maketrans("०१२३४५६७८९", "0123456789"),  # Devanagari
    str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"),  # Bengali
    str.maketrans("૦૧૨૩૪૫૬૭૮৯", "0123456789"),  # Gujarati
    str.maketrans("੦੧੨੃੪੫੬੭੮੯", "0123456789"),  # Gurmukhi
    str.maketrans("௦௧௨௩௪௫௬௭௮௯", "0123456789"),  # Tamil
    str.maketrans("౦౧౨౩౪౫౬౭౮౯", "0123456789"),  # Telugu
    str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789"),  # Kannada
    str.maketrans("൦൧൨൩൪൫൬൭൮൯", "0123456789"),  # Malayalam
]

# ================= NUMBER WORDS =================
def build_english_numbers():
    base = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16,
        "seventeen": 17, "eighteen": 18, "nineteen": 19
    }

    tens = {
        "twenty": 20, "thirty": 30, "forty": 40,
        "fifty": 50, "sixty": 60, "seventy": 70,
        "eighty": 80, "ninety": 90
    }

    numbers = {k: str(v) for k, v in base.items()}

    for t_word, t_val in tens.items():
        numbers[t_word] = str(t_val)
        for u_word, u_val in base.items():
            if u_val == 0:
                continue
            numbers[f"{t_word}{u_word}"] = str(t_val + u_val)
            numbers[f"{t_word} {u_word}"] = str(t_val + u_val)

    numbers["hundred"] = "100"
    numbers["onehundred"] = "100"
    return numbers


HINDI_ROMAN_NUMBERS = {
    "ek": "1", "do": "2", "teen": "3", "char": "4", "paanch": "5",
    "chhe": "6", "saat": "7", "aath": "8", "nau": "9", "das": "10",

    "gyarah": "11", "barah": "12", "terah": "13", "chaudah": "14",
    "pandrah": "15", "solah": "16", "satrah": "17",
    "atharah": "18", "unnees": "19",

    "bees": "20", "tees": "30", "chalees": "40",
    "pachaas": "50", "saath": "60", "sattar": "70",
    "assi": "80", "nabbe": "90",

    "sau": "100", "ekso": "100", "ek sau": "100"
}

BASE_NUMBER_WORDS = {}
BASE_NUMBER_WORDS.update(build_english_numbers())
BASE_NUMBER_WORDS.update(HINDI_ROMAN_NUMBERS)

NUMBER_WORDS_SORTED = sorted(
    BASE_NUMBER_WORDS.items(),
    key=lambda x: -len(x[0])
)

# ================= HELPERS =================
def collapse_vowels(text):
    return re.sub(r"([aeiou])\1+", r"\1", text)


def normalize(text):
    if not isinstance(text, str):
        return ""

    text = text.lower()
    for m in INDIAN_DIGIT_MAPS:
        text = text.translate(m)

    prev = None
    while prev != text:
        prev = text
        for w, d in NUMBER_WORDS_SORTED:
            text = re.sub(rf"(?<![a-z]){w}", d, text)

    return text


def expand_repetitions(text):
    text = re.sub(r"double\s*([0-9])", lambda m: m.group(1) * 2, text)
    text = re.sub(r"triple\s*([0-9])", lambda m: m.group(1) * 3, text)
    return text


def digit_stream(text):
    return re.sub(r"[^0-9]", "", expand_repetitions(text))


def valid_indian_mobile(num):
    return len(num) == 10 and num[0] in "6789"


# ================= REGEX =================
EMAIL_REGEX = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.I)
URL_REGEX = re.compile(r"(https?:\/\/|www\.)", re.I)
MAPS_REGEX = re.compile(r"(google\.com/maps|maps\.google\.com|maps\.app\.goo\.gl|goo\.gl/maps|maps\.apple\.com)", re.I)
PRICE_CONTEXT = re.compile(r"\b(emi|loan|lakh|lac|k\b|km|kms|month|year|yrs?)\b", re.I)

# ================= CLASSIFICATION =================
def classify_messages(texts):
    debug = {"normalized_text": "", "reconstructed_numbers": [], "rule_triggered": None}

    for msg in texts:
        norm = normalize(msg)
        norm_vowel = collapse_vowels(norm)

        streams = [
            ("original", digit_stream(norm)),
            ("vowel_collapsed", digit_stream(norm_vowel))
        ]

        debug["normalized_text"] = norm

        for mode, stream in streams:
            for i in range(len(stream) - 9):
                candidate = stream[i:i + 10]
                debug["reconstructed_numbers"].append(f"{candidate} ({mode})")

                if not valid_indian_mobile(candidate):
                    continue

                if re.search(r"[a-z]", msg.lower()):
                    debug["rule_triggered"] = f"Phone reconstructed using letters ({mode})"
                    return "MIXED_WORD_DIGIT_PHONE", debug

    joined = " ".join(texts).lower()

    if MAPS_REGEX.search(joined):
        return "MAPS_LINK_SHARED", debug
    if EMAIL_REGEX.search(joined):
        return "EMAIL_SHARED", debug
    if URL_REGEX.search(joined):
        return "NON_MAP_LINK_SHARED", debug
    if PRICE_CONTEXT.search(joined):
        return "PRICE_AMOUNT", debug

    return "NO_CONTACT_DETECTED", debug

# ================= STREAMLIT UI =================
st.set_page_config(page_title="Message Block Checker", layout="centered")
st.title("📩 Message Block Checker")

debug_mode = st.checkbox("🔍 Debug mode")

user_input = st.text_area("Paste message", height=160)

if st.button("Check Message"):
    category, debug = classify_messages([user_input])
    status = CATEGORY_POLICY[category]

    if status == "BLOCKED":
        st.error("🚫 BLOCKED")
    else:
        st.success("✅ ALLOWED")

    st.write("**Category:**", category)

    if debug_mode:
        st.code(debug)
