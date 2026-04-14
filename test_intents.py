import sys
import os
sys.path.append(r'c:\Users\majji\OneDrive\Desktop\GO 3 demo\GO 3\Go')

from intent_classifier import IntentClassifier
from config import Config

def test():
    ic = IntentClassifier()
    
    test_cases = [
        # English
        ('en', 'start detection', 'START_DETECTION'),
        ('en', 'navigate to hyderabad', 'NAVIGATE'),
        ('en', 'change language', 'CHANGE_LANGUAGE'),
        ('en', 'stop', 'STOP'),
        
        # Telugu
        ('te', 'డిటెక్షన్ ప్రారంభించు', 'START_DETECTION'),
        ('te', 'హైదరాబాద్‌కు నావిగేట్ చేయి', 'NAVIGATE'),
        ('te', 'భాష మార్చు', 'CHANGE_LANGUAGE'),
        ('te', 'ఆపు', 'STOP'),
        
        # Hindi
        ('hi', 'डिटेक्शन शुरू करो', 'START_DETECTION'),
        ('hi', 'हैदराबाद तक नेविगेशन।', 'NAVIGATE'),
        ('hi', 'भाषा बदलो', 'CHANGE_LANGUAGE'),
        ('hi', 'रुको', 'STOP'),
        
        # Tamil
        ('ta', 'கண்டறிதல் தொடங்கு', 'START_DETECTION'),
        ('ta', 'vazhi kaattu hyderabad', 'NAVIGATE'),
        ('ta', 'மொழி மாற்று', 'CHANGE_LANGUAGE'),
        ('ta', 'நிறுத்து', 'STOP'),
    ]
    
    print("--- INTENT CLASSIFICATION TESTS ---")
    all_passed = True
    for lang, cmd, expected in test_cases:
        actual = ic.classify_intent(cmd, lang)
        if actual == expected:
            print(f"[PASS] {lang.upper()}: '{cmd}' -> {actual}")
        else:
            print(f"[FAIL] {lang.upper()}: '{cmd}'. Expected {expected}, got {actual}")
            all_passed = False
            
    # Test Language Resolution
    print("\n--- LANGUAGE ALIAS TESTS ---")
    lang_cases = [
        ('Telugu', 'te'),
        ('తెలుగు', 'te'),
        ('Hindi', 'hi'),
        ('हिंदी', 'hi'),
        ('Tamil', 'ta'),
        ('தமிழ்', 'ta'),
        ('English', 'en'),
    ]
    
    for cmd, expected in lang_cases:
        actual = ic.resolve_language(cmd)
        if actual == expected:
            print(f"[PASS] Resolve '{cmd}' -> {actual}")
        else:
            print(f"[FAIL] Resolve '{cmd}'. Expected {expected}, got {actual}")
            all_passed = False
            
    # Test Destination Extraction
    print("\n--- DESTINATION EXTRACTION TESTS ---")
    dest_cases = [
        ('navigate to hyderabad', 'hyderabad'),
        ('go to the nearest hospital', 'the nearest hospital'),
        ('hyderabad ku daari chupinchu', 'hyderabad'),
        ('supermarket ki daari chupinchu', 'supermarket'),
        ('bank ko rasta dikhao', 'bank'),
        ('navigate cheyi vizag', 'vizag'),
        ('rasta dikhao delhi', 'delhi'),
        ('vazhi kaattu chennai', 'chennai'),
    ]
    for cmd, expected in dest_cases:
        actual = ic.extract_destination(cmd)
        if actual == expected:
             print(f"[PASS] Destination '{cmd}' -> {actual}")
        else:
             print(f"[FAIL] Destination '{cmd}'. Expected {expected}, got {actual}")
             all_passed = False
             
    if all_passed:
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED!")

if __name__ == '__main__':
    test()
