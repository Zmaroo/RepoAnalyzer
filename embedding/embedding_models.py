import torch
from transformers import AutoTokenizer, AutoModel
from sentence_transformers import SentenceTransformer

class CodeEmbedder:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("microsoft/graphcodebert-base")
        self.model = AutoModel.from_pretrained("microsoft/graphcodebert-base")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    def embed(self, code_text: str):
        inputs = self.tokenizer(code_text, return_tensors="pt", truncation=True, max_length=512)
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with torch.no_grad():
            outputs = self.model(**inputs)
        # Use the CLS-token embedding as a representation.
        embedding = outputs.last_hidden_state[:, 0, :].squeeze().cpu().numpy()
        return embedding

class DocEmbedder:
    def __init__(self):
        self.model = SentenceTransformer("all-mpnet-base-v2")

    def embed(self, text: str):
        embedding = self.model.encode(text)
        return embedding
