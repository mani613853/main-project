"""Intent classification for voice commands - fully language-aware.

Uses Config.VOICE_COMMANDS which is now a nested dict keyed by language code.
The VoiceEngine.current_language determines which command set to match against.
"""
import re
from config import Config


class IntentClassifier:
    def __init__(self):
        self.all_commands = Config.VOICE_COMMANDS
        self.language_aliases = Config.LANGUAGE_ALIASES

    def _get_commands(self, language: str) -> dict:
        """Return the command dict for the given language, falling back to English."""
        return self.all_commands.get(language, self.all_commands.get('en', {}))

    def classify_intent(self, command: str, language: str = 'en') -> str | None:
        if not command:
            return None
        cmd = command.lower().strip()

        # Filter out very short or known ignored words
        ignore_words = {'navigation', 'destination', 'starting', 'mode',
                        'please', 'now', 'say', 'your'}
        if cmd in ignore_words or len(cmd) < 3:
            return None

        commands = self._get_commands(language)
        for intent, phrases in commands.items():
            for phrase in phrases:
                if phrase.lower() in cmd:
                    return intent
        return None

    def resolve_language(self, command: str) -> str | None:
        """Returns the language code if the command is a language name, else None."""
        cmd = command.lower().strip()
        for lang_code, aliases in self.language_aliases.items():
            for alias in aliases:
                if alias.lower() in cmd or cmd in alias.lower():
                    return lang_code
        return None

    def extract_destination(self, command: str) -> str | None:
        """Extract destination from navigation command."""
        skip = {'navigate', 'navigation', 'go', 'to', 'me', 'take',
                'cheyi', 'prarambhinchu', 'shuru', 'karo', 'thodangu'}
        
        # Order matters: longer, more specific phrases first.
        prefix_patterns = [
            # English
            r'take me to (.+)',
            r'navigate to (.+)',
            r'my destination is (.+)',
            r'destination is (.+)',
            r'my destination (.+)',
            r'go to (.+)',
            # Telugu
            r'navigate cheyi (.+)',
            r'daari chupinchu (.+)',
            r'నావిగేట్ చేయి (.+)',
            r'దారి చూపించు (.+)',
            r'navigate (.+)',            r'నావిగేట్ చేయి (.+)',
            r'దారి చూపించు (.+)',
            # Hindi
            r'navigation shuru karo (.+)',
            r'rasta dikhao (.+)',
            r'नेविगेशन शुरू करो (.+)',
            r'रास्ता दिखाओ (.+)',
            # Tamil
            r'navigation thodangu (.+)',
            r'vazhi kaattu (.+)',
            r'வழி காட்டு (.+)',
        ]
        
        suffix_patterns = [
            # Telugu (e.g., "hyderabad ku daari chupinchu")
            r'(.+?)\s*(?:ku |ki |)(?:daari chupinchu|navigate cheyi|కి దారి చూపించు|కు దారి చూపించు|నావిగేట్ చేయి)',
            # Hindi (e.g., "delhi tak rasta dikhao")
            r'(.+?)\s*(?:tak |ko |)(?:rasta dikhao|navigation shuru karo|तक रास्ता दिखाओ|को रास्ता दिखाओ)',
            # Tamil (e.g., "chennai ikku vazhi kaattu")
            r'(.+?)\s*(?:ikku |ukku |)(?:vazhi kaattu|navigation thodangu|க்கு வழி காட்டு)'
        ]
        
        cmd = command.lower().strip()
        
        # 1. Try prefix patterns first ("navigate to X")
        for p in prefix_patterns:
            m = re.search(p, cmd, re.IGNORECASE)
            if m:
                dest = m.group(1).strip()
                if dest and dest not in skip and len(dest) > 2:
                    return dest
                    
        # 2. Try suffix patterns ("X ku daari chupinchu")
        for p in suffix_patterns:
            m = re.search(p, cmd, re.IGNORECASE)
            if m:
                dest = m.group(1).strip()
                if dest and dest not in skip and len(dest) > 2:
                    return dest
                    
        return None
