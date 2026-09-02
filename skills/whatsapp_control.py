import logging

logger = logging.getLogger(__name__)


class WhatsAppControlSkill:
    """
    Skill for sending WhatsApp messages via pywhatkit by automating WhatsApp Web in the browser.
    """
    def __init__(self, config: dict):
        self.config = config
        whatsapp_cfg = config.get("whatsapp", {})
        self.enabled = whatsapp_cfg.get("enabled", True)
        self.contacts = whatsapp_cfg.get("contacts", {})
        self.wait_time = int(whatsapp_cfg.get("wait_time", 10))
        self.honorific = config.get("assistant", {}).get("user_honorific", "boss")

    def send_message(self, contact_name: str, message: str) -> str:
        """
        Looks up contact, opens WhatsApp Web via pywhatkit, and sends the message.

        Args:
            contact_name (str): The name of the contact as requested by user.
            message (str): The message text to send.

        Returns:
            str: Spoken confirmation or error message.
        """
        if not self.enabled:
            logger.info("WhatsApp send attempt failed: WhatsApp control is disabled in configuration.")
            return f"WhatsApp messaging is currently disabled in your configuration, {self.honorific}."

        if not contact_name or not contact_name.strip():
            logger.info("WhatsApp send attempt failed: Contact name is empty.")
            return f"Please specify a contact name, {self.honorific}."

        if not message or not message.strip():
            logger.info(f"WhatsApp send attempt failed for contact '{contact_name}': Message content is empty.")
            return f"What message would you like me to send to {contact_name}, {self.honorific}?"

        clean_contact = contact_name.strip().lower()
        message_text = message.strip()
        msg_len = len(message_text)

        # 1. Look up contact in mapping (exact or substring match)
        phone_number = self.contacts.get(clean_contact)
        matched_name = clean_contact

        if not phone_number:
            for key, val in self.contacts.items():
                if key.lower() in clean_contact or clean_contact in key.lower():
                    phone_number = val
                    matched_name = key
                    break

        # Handle unconfigured contacts, missing numbers, or placeholder numbers (e.g. "+91XXXXXXXXXX")
        if not phone_number or "X" in str(phone_number).upper():
            logger.info(
                f"WhatsApp send attempt for Contact='{clean_contact}', MsgLength={msg_len} - "
                f"Status: Failure (Contact not found or invalid number in config)"
            )
            return f"I couldn't find a valid phone number for {contact_name} in your contacts, {self.honorific}."

        logger.info(
            f"Initiating WhatsApp send attempt: Contact='{matched_name}', Phone='{phone_number}', "
            f"MsgLength={msg_len}, WaitTime={self.wait_time}s"
        )

        # 2. Attempt sending via pywhatkit
        try:
            import pywhatkit
            
            # sendwhatmsg_instantly opens WhatsApp Web with parameters pre-filled and presses Enter
            pywhatkit.sendwhatmsg_instantly(
                phone_no=str(phone_number),
                message=message_text,
                wait_time=self.wait_time,
                tab_close=True,
                close_time=3
            )

            logger.info(
                f"WhatsApp send attempt for Contact='{matched_name}', MsgLength={msg_len} - "
                f"Status: Success"
            )
            return f"Message sent to {matched_name}, {self.honorific}."

        except ModuleNotFoundError:
            logger.error(
                f"WhatsApp send attempt for Contact='{matched_name}', MsgLength={msg_len} - "
                f"Status: Failure (pywhatkit library not installed)"
            )
            return f"The pywhatkit library is not installed, {self.honorific}."

        except Exception as e:
            err_str = str(e).lower()
            logger.error(
                f"WhatsApp send attempt for Contact='{matched_name}', MsgLength={msg_len} - "
                f"Status: Failure (Error: {e})",
                exc_info=True
            )

            if "not authorized" in err_str or "qr" in err_str or "login" in err_str:
                return f"WhatsApp Web is not authorized in your browser, {self.honorific}. Please scan the QR code to log in."
            elif "countrycode" in err_str or "country code" in err_str:
                return f"The phone number for {matched_name} is missing a country code, {self.honorific}."
            else:
                return f"Failed to send WhatsApp message to {matched_name}, {self.honorific}."
