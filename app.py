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
    "०१२३४५६७८९"  # Devanagari (Hindi, Marathi, Nepali)
    "০১২৩৪৫৬৭৮৯"  # Bengali
    "૦૧૨૩૪૫૬૭૮૯"  # Gujarati
    "੦੧੨੩੪੫੬੭੮੯"  # Gurmukhi (Punjabi)
    "௦௧௨௩௪௫௬௭௮௯"  # Tamil
    "౦౧౨౩౪౫౬౭౮౯"  # Telugu
    "೦೧೨೩೪೫೬೭೮೯"  # Kannada
    "൦൧൨൩൪൫൬൭൮൯", # Malayalam
    "0123456789" * 8
)

NUMBER_WORDS = {
    "zero":"0","one":"1","two":"2","three":"3","four":"4",
    "five":"5","six":"6","seven":"7","eight":"8","nine":"9",
    "ek":"1","do":"2","teen":"3","char":"4","paanch":"5",
    "chhe":"6","saat":"7","aath":"8","nau":"9"
}

EMAIL_REGEX = re.compile(r'[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}', re.I)
URL_REGEX = re.compile(r'(https?:\/\/|www\.)', re.I)

MAPS_REGEX = re.compile(
    r'(google\.com/maps|maps\.google\.com|maps\.app\.goo\.gl|goo\.gl/maps|maps\.apple\.com)',
    re.I
)

PRICE_CONTEXT = re.compile(
    r'\b(emi|loan|lakh|lac|l\b|k\b|km|kms|month|months|year|years|yrs?)\b',
    re.I
)

# ================= HELPERS =================
def normalize(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = text.translate(INDIAN_DIGITS)
    text = re.sub(r'([aeiou])\1+', r'\1', text)

    # number words even when glued
    for w, d in NUMBER_WORDS.items():
        text = re.sub(rf"(?<![a-z]){w}(?![a-z])", d, text)

    return text

def expand_repetitions(text):
    text = re.sub(r'double\s*([0-9])', lambda m: m.group(1) * 2, text)
    text = re.sub(r'triple\s*([0-9])', lambda m: m.group(1) * 3, text)
    text = re.sub(r'doublenine', '99', text)
    text = re.sub(r'triplenine', '999', text)
    return text

def digit_stream(text):
    return re.sub(r'[^0-9]', '', expand_repetitions(normalize(text)))

def valid_indian_mobile(num):
    return len(num) == 10 and num[0] in "6789"

def extract_digit_chunks(msg):
    if PRICE_CONTEXT.search(msg.lower()):
        return []
    return re.findall(r'\d{2,6}', msg)

# ================= MULTI MESSAGE DETECTION =================
def detect_multi_message_phone(texts, window=3):
    n = len(texts)
    for i in range(n):
        combined = ""
        for j in range(i, min(i + window, n)):
            chunks = extract_digit_chunks(texts[j])
            if not chunks:
                break
            for c in chunks:
                combined += c
                if len(combined) == 10 and valid_indian_mobile(combined):
                    return True
                if len(combined) > 10:
                    break
    return False

# ================= COMPACT REPETITION DETECTION =================
def is_compact_repetition(stream):
    if len(stream) < 10:
        return False

    for i in range(len(stream) - 9):
        s = stream[i:i+10]

        # same digit repeated
        if len(set(s)) == 1:
            return True

        # alternating pattern (e.g. 9898989898)
        if s[0::2] == s[1::2]:
            return True

    return False

# ================= CLASSIFICATION =================
def classify_messages(texts):
    for msg in texts:
        stream = digit_stream(msg)

        if is_compact_repetition(stream):
            return "COMPACT_REPETITION_PHONE"

        for i in range(len(stream) - 9):
            if not valid_indian_mobile(stream[i:i+10]):
                continue

            if re.search(r'\b[6-9]\d{9}\b', msg):
                return "DIRECT_PHONE_NUMBER"

            if re.search(r'\d[^a-zA-Z0-9\s]+\d', msg):
                return "SYMBOL_SEPARATED_PHONE"

            if re.search(r'[a-zA-Z]', msg):
                return "MIXED_WORD_DIGIT_PHONE"

            if re.search(r'double|triple', msg.lower()):
                return "DOUBLE_TRIPLE_EXPANSION_PHONE"

            return "MULTI_EVASION_SINGLE_MESSAGE"

    if detect_multi_message_phone(texts):
        return "MULTI_MESSAGE_DIGIT_SPLIT"

    joined = " ".join(texts)

    if MAPS_REGEX.search(joined):
        return "MAPS_LINK_SHARED"

    if EMAIL_REGEX.search(joined):
        return "EMAIL_SHARED"

    if URL_REGEX.search(joined):
        return "NON_MAP_LINK_SHARED"

    if PRICE_CONTEXT.search(joined):
        return "PRICE_AMOUNT"

    if re.search(r'\b(19|20)\d{2}\b', joined):
        return "YEAR_REFERENCE"

    if re.search(r'\b\d+\.\d+\b', joined):
        return "SAFE_DECIMAL"

    if re.search(r'\b\d{5,6}\b', joined):
        return "GENERIC_NUMBER"

    return "NO_CONTACT_DETECTED"

# ================= STREAMLIT UI =================
st.set_page_config(page_title="Message Block Checker", layout="centered")
st.title("📩 Message Block Checker")

user_input = st.text_area(
    "Paste message to check",
    height=160,
    placeholder="Enter message text here..."
)

if st.button("Check Message"):
    if not user_input.strip():
        st.warning("Please enter a message.")
    else:
        category = classify_messages([user_input])
        status = CATEGORY_POLICY[category]

        if status == "BLOCKED":
            st.error("🚫 Message Status: BLOCKED")
            st.write(f"**Blocked Reason:** {category}")
        else:
            st.success("✅ Message Status: ALLOWED")
            st.write(f"**Reason:** {category}")