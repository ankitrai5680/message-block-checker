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

INDIAN_DIGITS = str.maketrans(
    "०१२३४५६७८९"  # Devanagari
    "০১২৩৪৫৬৭८৯"  # Bengali
    "૦૧૨૩૪૫૬૭૮৯"  # Gujarati
    "੦੧੨੩੪੫੬੭੮੯"  # Gurmukhi
    "௦௧௨௩௪௫௬௭௮௯"  # Tamil
    "౦౧౨౩౪౫౬౭౮౯"  # Telugu
    "೦೧೨೩೪೫೬೭೮೯"  # Kannada
    "൦൧൨൩൪൫൬൭൮൯", # Malayalam
    "0123456789" * 8
)

# ================= NUMBER WORDS =================
NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10",            # 🔥 critical fix
    "ek": "1", "do": "2", "teen": "3", "char": "4", "paanch": "5",
    "chhe": "6", "saat": "7", "aath": "8", "nau": "9"
}

NUMBER_WORDS_SORTED = sorted(NUMBER_WORDS.items(), key=lambda x: -len(x[0]))

EMAIL_REGEX = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.I)
URL_REGEX = re.compile(r"(https?:\/\/|www\.)", re.I)

MAPS_REGEX = re.compile(
    r"(google\.com/maps|maps\.google\.com|maps\.app\.goo\.gl|goo\.gl/maps|maps\.apple\.com)",
    re.I
)

PRICE_CONTEXT = re.compile(
    r"\b(emi|loan|lakh|lac|l\b|k\b|km|kms|month|months|year|years|yrs?)\b",
    re.I
)

# ================= NORMALIZATION =================
def normalize(text):
    if not isinstance(text, str):
        return ""

    text = text.lower()
    text = text.translate(INDIAN_DIGITS)
    text = re.sub(r"([aeiou])\1+", r"\1", text)

    prev = None
    while prev != text:
        prev = text
        for w, d in NUMBER_WORDS_SORTED:
            text = re.sub(rf"(?<![a-z]){w}(?![a-z])", d, text)

    return text

def expand_repetitions(text):
    text = re.sub(r"double\s*([0-9])", lambda m: m.group(1) * 2, text)
    text = re.sub(r"triple\s*([0-9])", lambda m: m.group(1) * 3, text)
    text = re.sub(r"doublenine", "99", text)
    text = re.sub(r"triplenine", "999", text)
    return text

def digit_stream(text):
    return re.sub(r"[^0-9]", "", expand_repetitions(text))

def valid_indian_mobile(num):
    return len(num) == 10 and num[0] in "6789"

# ================= CLASSIFICATION =================
def classify_messages(texts):
    debug = {
        "normalized_text": "",
        "reconstructed_numbers": [],
        "rule_triggered": None
    }

    for msg in texts:
        norm = normalize(msg)
        stream = digit_stream(norm)
        debug["normalized_text"] = norm

        for i in range(len(stream) - 9):
            candidate = stream[i:i + 10]
            debug["reconstructed_numbers"].append(candidate)

            if not valid_indian_mobile(candidate):
                continue

# ✅ NEW (CRITICAL FIX)
            if re.search(r"[a-z]", msg.lower()):
                debug["rule_triggered"] = "Valid phone reconstructed using letters"
                return "MIXED_WORD_DIGIT_PHONE", debug

            if re.search(r"\b[6-9]\d{9}\b", norm):
                debug["rule_triggered"] = "Direct phone number"
                return "DIRECT_PHONE_NUMBER", debug

            if re.search(r"\d[^a-z0-9\s]+\d", norm):
                debug["rule_triggered"] = "Symbol separated digits"
                return "SYMBOL_SEPARATED_PHONE", debug

            if re.search(r"double|triple", norm):
                debug["rule_triggered"] = "Double / triple expansion"
                return "DOUBLE_TRIPLE_EXPANSION_PHONE", debug

            debug["rule_triggered"] = "Generic evasion with valid phone"
            return "MULTI_EVASION_SINGLE_MESSAGE", debug

    joined = " ".join(texts).lower()

    if MAPS_REGEX.search(joined):
        debug["rule_triggered"] = "Maps link allowed"
        return "MAPS_LINK_SHARED", debug

    if EMAIL_REGEX.search(joined):
        debug["rule_triggered"] = "Email detected"
        return "EMAIL_SHARED", debug

    if URL_REGEX.search(joined):
        debug["rule_triggered"] = "Non-maps URL detected"
        return "NON_MAP_LINK_SHARED", debug

    if PRICE_CONTEXT.search(joined):
        debug["rule_triggered"] = "Price / finance context"
        return "PRICE_AMOUNT", debug

    if re.search(r"\b(19|20)\d{2}\b", joined):
        debug["rule_triggered"] = "Year reference"
        return "YEAR_REFERENCE", debug

    if re.search(r"\b\d+\.\d+\b", joined):
        debug["rule_triggered"] = "Safe decimal"
        return "SAFE_DECIMAL", debug

    if re.search(r"\b\d{5,6}\b", joined):
        debug["rule_triggered"] = "Generic numeric"
        return "GENERIC_NUMBER", debug

    debug["rule_triggered"] = "No contact detected"
    return "NO_CONTACT_DETECTED", debug

# ================= STREAMLIT UI =================
st.set_page_config(page_title="Message Block Checker", layout="centered")
st.title("📩 Message Block Checker")

debug_mode = st.checkbox("🔍 Debug mode (show internals)")

user_input = st.text_area(
    "Paste message to check",
    height=160,
    placeholder="Enter message text here..."
)

if st.button("Check Message"):
    if not user_input.strip():
        st.warning("Please enter a message.")
    else:
        category, debug = classify_messages([user_input])
        status = CATEGORY_POLICY[category]

        if status == "BLOCKED":
            st.error("🚫 Message Status: BLOCKED")
        else:
            st.success("✅ Message Status: ALLOWED")

        st.write(f"**Category:** {category}")
        st.write(f"**Rule Triggered:** {debug['rule_triggered']}")

        if debug_mode:
            st.markdown("### 🔎 Debug details")
            st.write("**Normalized text:**")
            st.code(debug["normalized_text"])
            st.write("**Reconstructed digit candidates:**")
            st.code(", ".join(debug["reconstructed_numbers"]) or "None")
