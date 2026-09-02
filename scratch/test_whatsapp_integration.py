import sys
import os
import yaml
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from skills.whatsapp_control import WhatsAppControlSkill
from core.router import CommandRouter
from core.intent_classifier import IntentClassifier

# Set up logging output to stdout
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(name)s - %(message)s")

def test_whatsapp_skill():
    print("\n--- Testing WhatsAppControlSkill ---")
    config = {
        "assistant": {"user_honorific": "boss"},
        "whatsapp": {
            "enabled": True,
            "contacts": {
                "mom": "+91XXXXXXXXXX",
                "ragul": "+919876543210"
            },
            "wait_time": 10
        }
    }
    skill = WhatsAppControlSkill(config)

    # Test 1: Contact not in mapping
    resp = skill.send_message("unknown_contact", "hello")
    print(f"Unknown contact response: {resp}")
    assert "couldn't find a valid phone number for unknown_contact" in resp

    # Test 2: Placeholder contact number
    resp = skill.send_message("mom", "hello")
    print(f"Placeholder contact response: {resp}")
    assert "couldn't find a valid phone number for mom" in resp

    # Test 3: Empty contact name
    resp = skill.send_message("", "hello")
    print(f"Empty contact response: {resp}")
    assert "specify a contact name" in resp

    # Test 4: Empty message
    resp = skill.send_message("ragul", "")
    print(f"Empty message response: {resp}")
    assert "What message would you like me to send to ragul" in resp

    # Test 5: Disabled skill
    config["whatsapp"]["enabled"] = False
    disabled_skill = WhatsAppControlSkill(config)
    resp = disabled_skill.send_message("ragul", "hello")
    print(f"Disabled skill response: {resp}")
    assert "disabled" in resp

    print("WhatsAppControlSkill unit tests PASSED!")

def test_whatsapp_regex_routing():
    print("\n--- Testing WhatsApp CommandRouter Regex Routing ---")
    with open(os.path.join(os.path.dirname(__file__), "..", "config.yaml"), "r") as f:
        config = yaml.safe_load(f)

    # Disable intent classification for fast exact layer 1 test
    config["intent_classification"]["enabled"] = False
    router = CommandRouter(config)

    test_cases = [
        ("send a whatsapp message to mom saying hello how are you", "mom", "hello how are you"),
        ("whatsapp ragul saying meet me at 5", "ragul", "meet me at 5"),
        ("send dad a message saying i will be home soon", "dad", "i will be home soon"),
        ("message mom saying call me", "mom", "call me"),
        ("send mom a whatsapp message saying hello", "mom", "hello"),
        ("send whatsapp to dad saying good morning", "dad", "good morning")
    ]

    for cmd, expected_contact, expected_msg in test_cases:
        resp = router.route(cmd)
        print(f"Command: '{cmd}' -> Response: '{resp}'")
        assert f"couldn't find a valid phone number for {expected_contact}" in resp or "Message sent" in resp

    print("WhatsApp Regex Routing tests PASSED!")

def test_intent_classifier_entity_extraction():
    print("\n--- Testing IntentClassifier Entity Extraction ---")
    test_cases = [
        ("send a whatsapp message to mom saying hello", "mom", "hello"),
        ("whatsapp ragul saying meet me at 5", "ragul", "meet me at 5"),
        ("send dad a message saying i will be home soon", "dad", "i will be home soon"),
        ("send a whatsapp to mom", "mom", ""),
        ("message dad on whatsapp", "dad", "")
    ]

    for cmd, exp_contact, exp_msg in test_cases:
        contact, msg = IntentClassifier.extract_whatsapp_entities(cmd)
        print(f"Cmd: '{cmd}' -> Contact: '{contact}', Msg: '{msg}'")
        assert contact == exp_contact, f"Expected contact '{exp_contact}', got '{contact}'"
        assert msg == exp_msg, f"Expected msg '{exp_msg}', got '{msg}'"

    print("IntentClassifier Entity Extraction tests PASSED!")

if __name__ == "__main__":
    test_whatsapp_skill()
    test_whatsapp_regex_routing()
    test_intent_classifier_entity_extraction()
    print("\nAll WhatsApp tests executed successfully!")
