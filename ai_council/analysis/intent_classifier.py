from sentence_transformers import SentenceTransformer, util

class IntentClassifier:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

        self.intent_examples = {
            "QUESTION": [
                "What is Python?",
                "How does this work?"
            ],
            "ANALYSIS": [
                "Compare PostgreSQL and MongoDB",
                "What are the trade-offs?"
            ],
            "INSTRUCTION": [
                "Write a Python program",
                "Create a function"
            ],
            "CREATION": [
                "Create a website",
                "Build a project",
                "Generate code"
            ],
            "MODIFICATION": [
                "Modify this code",
                "Update the function",
                "Improve this script"
            ],
            "VERIFICATION": [
                "Check if this is correct",
                "Validate this output",
                "Is this right?"
            ]
        }

        self.intent_embeddings = {
            intent: self.model.encode(examples, convert_to_tensor=True)
            for intent, examples in self.intent_examples.items()
        }

    def classify(self, text):
        query_embedding = self.model.encode(text, convert_to_tensor=True)

        best_intent = None
        best_score = -1

        for intent, embeddings in self.intent_embeddings.items():
            scores = util.cos_sim(query_embedding, embeddings)
            score = scores.max().item()

            if score > best_score:
                best_score = score
                best_intent = intent

        return best_intent if best_intent else "INSTRUCTION"