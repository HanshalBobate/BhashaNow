import easyocr

language_init = {
    'urdu':'ur', 'hindi':'hi','marathi':'hi','nepali':'hi',
    'telugu':'te','kannada':'kn','bengali':'bn','assamese':'bn'
}

# Script mapping for Aksharamukha
languages = {
    "english": "IAST",
    "hindi": "Devanagari",
    "marathi": "Devanagari",
    "nepali": "Devanagari",
    "urdu": "Arabic",
    "telugu": "Telugu",
    "kannada": "Kannada",
    "bengali": "Bengali",
    "assamese": "Bengali"
}
while 1:
    try:
        print("UR . . . ")
        easyocr.Reader(['ur'], gpu = False)
        print("HI . . . ")
        easyocr.Reader(['hi'], gpu = False)
        print("TE . . . ")
        easyocr.Reader(['te'], gpu = False)
        print("KN . . . ")
        easyocr.Reader(['kn'], gpu = False)
        print("BN . . . ")
        easyocr.Reader(['bn'], gpu = False)
    except Exception as e:
        print("Exception Occured")
    print("Loop again")