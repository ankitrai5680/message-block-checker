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

# ================= DIGIT NORMALISATION =================
INDIAN_DIGIT_MAPS = [
    str.maketrans("०१२३४५६७८९", "0123456789"),
    str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"),
    str.maketrans("૦૧૨૩૪૫૬૭૮৯", "0123456789"),
    str.maketrans("੦੧੨੩੪੫੬੭੮੯", "0123456789"),
    str.maketrans("௦௧௨௩௪௫௬௭௮௯", "0123456789"),
    str.maketrans("౦౧౨౩౪౫౬౭౮౯", "0123456789"),
    str.maketrans("೦೧੨೩೪೫೬೭೮೯", "0123456789"),
    str.maketrans("൦൧൨൩൪൫൬൭൮൯", "0123456789"),
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

    out = {k: str(v) for k, v in base.items()}
    for t, tv in tens.items():
        out[t] = str(tv)
        for u, uv in base.items():
            if uv > 0:
                out[f"{t}{u}"] = str(tv + uv)
                out[f"{t} {u}"] = str(tv + uv)
    return out


HINDI_ROMAN_NUMBERS = {
    "ek":"1","do":"2","teen":"3","char":"4","paanch":"5",
    "chhe":"6","saat":"7","aath":"8","nau":"9","das":"10",
    "gyarah":"11","barah":"12","terah":"13","chaudah":"14",
    "pandrah":"15","solah":"16","satrah":"17","atharah":"18","unnees":"19",
    "bees":"20","tees":"30","chalees":"40","pachaas":"50",
    "saath":"60","sattar":"70","assi":"80","nabbe":"90"
}

NUMBER_WORDS = {}
NUMBER_WORDS.update(build_english_numbers())
NUMBER_WORDS.update(HINDI_ROMAN_NUMBERS)

NUMBER_WORDS_SORTED = sorted(NUMBER_WORDS.items(), key=lambda x: -len(x[0]))

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

def digit_stream(text):
    return re.sub(r"[^0-9]", "", text)

def valid_indian_mobile(num):
    return len(num) == 10 and num[0] in "6789"

# ================= REGEX =================
EMAIL_REGEX = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.I)
URL_REGEX = re.compile(r"(https?:\/\/|www\.)", re.I)
MAPS_REGEX = re.compile(r"(google\.com/maps|maps\.google\.com|goo\.gl/maps)", re.I)
PRICE_CONTEXT = re.compile(r"\b(emi|loan|lakh|lac|km|kms|year|yrs?)\b", re.I)

# ================= CLASSIFICATION =================
def classify_messages(texts):
    confidence = 0
    debug = {
        "reconstructed_numbers": [],
        "confidence_breakdown": []
    }

    for msg in texts:
        norm = normalize(msg)
        norm_collapsed = collapse_vowels(norm)

        for mode, text in [("original", norm), ("vowel_collapsed", norm_collapsed)]:
            digits = digit_stream(text)
            for i in range(len(digits) - 9):
                candidate = digits[i:i+10]
                if valid_indian_mobile(candidate):
                    confidence += 50
                    debug["confidence_breakdown"].append("Valid Indian mobile (+50)")
                    debug["reconstructed_numbers"].append(f"{candidate} ({mode})")

                    if re.search(r"[a-z]", msg.lower()):
                        confidence += 10
                        debug["confidence_breakdown"].append("Letters mixed with digits (+10)")

                    if mode == "vowel_collapsed":
                        confidence -= 10
                        debug["confidence_breakdown"].append("Caught via vowel collapse (-10)")

                    if len(debug["reconstructed_numbers"]) > 1:
                        confidence += 10
                        debug["confidence_breakdown"].append("Multiple reconstructions (+10)")

                    return "MIXED_WORD_DIGIT_PHONE", min(confidence, 100), debug

    joined = " ".join(texts).lower()

    if EMAIL_REGEX.search(joined):
        return "EMAIL_SHARED", 80, debug

    if MAPS_REGEX.search(joined):
        return "MAPS_LINK_SHARED", 80, debug

    if PRICE_CONTEXT.search(joined):
        return "PRICE_AMOUNT", 10, debug

    return "NO_CONTACT_DETECTED", 0, debug

# ================= STREAMLIT UI =================
st.set_page_config(page_title="Message Block Checker", layout="centered")
st.title("📩 Message Block Checker")

debug_mode = st.checkbox("🔍 Debug mode")

msg = st.text_area("Paste message to check", height=160)

if st.button("Check Message"):
    category, confidence, debug = classify_messages([msg])
    status = CATEGORY_POLICY.get(category, "ALLOWED")

    st.write(f"### Confidence Score: **{confidence}%**")

    if confidence == 0:
        st.success("✅ ALLOWED")
    elif confidence < 70:
        st.warning("⚠️ WARNING – Low confidence, needs review")
    else:
        if status == "BLOCKED":
            st.error("🚫 BLOCKED")
        else:
            st.success("✅ ALLOWED")

    st.write("**Category:**", category)

    if debug_mode:
        st.json(debug)
