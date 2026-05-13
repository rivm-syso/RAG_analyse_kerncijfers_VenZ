"""This file is meant for the ai connection. This file has not been tested as internally within RIVM we use a different document. See documentation provided if this implementation doesnt work. """
import openai
import langchain_openai

# See: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/supported-languages?tabs=dotnet-secure%2Csecure%2Cpython-entra&pivots=programming-language-python

# And: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses?tabs=python-key
class AI_CONNECTION:
    def __init__(self):
        self._version = '1.0'

            
    def OpenAI(self, authorization_file_path, config={}):
        self._authorize(authorization_file_path, ['ENDPOINT', 'API_KEY'])
        self._check_config(config, [], [])
        return openai.OpenAI(
            base_url=self.authorization['ENDPOINT'] + 'openai/v1/',
            api_key=self.authorization['API_KEY'],

        )