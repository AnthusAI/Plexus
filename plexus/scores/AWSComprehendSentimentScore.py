import os
import rich
from plexus.CustomLogging import logging
from plexus.scores.Score import Score
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError


class AWSComprehendSentimentScore(Score):
    """
    Score that uses AWS Comprehend to detect sentiment in text.
    
    This score analyzes the sentiment of input text using AWS Comprehend's
    detect_sentiment API. It returns one of four sentiment values:
    - POSITIVE: Text expresses positive sentiment
    - NEGATIVE: Text expresses negative sentiment
    - NEUTRAL: Text is neutral or factual
    - MIXED: Text contains both positive and negative sentiment
    
    The score automatically truncates input text to AWS Comprehend's limit
    of 5000 UTF-8 bytes.
    
    Example YAML configuration:
        - name: Customer Sentiment
          class: AWSComprehendSentimentScore
          data:
            processors:
              - class: FilterCustomerOnlyProcessor
              - class: RemoveSpeakerIdentifiersTranscriptFilter
    
    Note: Requires AWS credentials to be configured (via environment variables,
    AWS config file, or IAM role).
    """

    def __init__(self, **parameters):
        super().__init__(**parameters)
        # Initialize AWS Comprehend client
        region = os.getenv('AWS_REGION_NAME', 'us-east-1')
        self.comprehend_client = boto3.client('comprehend', region_name=region)
        
        # AWS Comprehend's text limit is 5000 UTF-8 bytes
        self.max_bytes = 5000
    
    @classmethod
    async def create(cls, **parameters):
        """
        Async factory method for creating score instances.
        
        This method is called by Scorecard when instantiating scores from API configurations.
        Since AWSComprehendSentimentScore doesn't require async initialization, we just
        create and return the instance.
        """
        return cls(**parameters)

    class Result(Score.Result):
        """
        Result structure for sentiment classification.
        
        Attributes:
            value: Sentiment label (POSITIVE, NEGATIVE, NEUTRAL, or MIXED)
            explanation: Detailed explanation including confidence scores
        """
        ...

    async def predict(self, context, model_input: Score.Input):
        """
        Predict sentiment using AWS Comprehend.
        
        Args:
            context: Prediction context (unused)
            model_input: Score.Input containing text to analyze
            
        Returns:
            Score.Result with sentiment value and confidence scores
        """
        rich.print("[b][magenta1]AWSComprehendSentimentScore[/magenta1][/b]")
        
        # Get text from input
        text = model_input.text
        
        # Truncate text if it exceeds AWS Comprehend's limit
        truncated_text = self._truncate_to_byte_limit(text, self.max_bytes)
        
        if len(text.encode('utf-8')) > self.max_bytes:
            original_length = len(text.encode('utf-8'))
            truncated_length = len(truncated_text.encode('utf-8'))
            logging.warning(
                f"Text truncated from {original_length} bytes to {truncated_length} bytes "
                f"to fit AWS Comprehend's limit of {self.max_bytes} bytes"
            )
        
        # Detect sentiment
        sentiment, sentiment_scores = self._detect_sentiment(truncated_text)
        
        # Get confidence for the detected sentiment
        # sentiment_scores keys are capitalized (Positive, Negative, Neutral, Mixed)
        confidence = sentiment_scores.get(sentiment.capitalize(), 0.0)
        
        # Format explanation with confidence scores
        explanation = self._format_explanation(sentiment, sentiment_scores, len(text.encode('utf-8')))
        
        return self.Result(
            parameters=self.parameters,
            value=sentiment,
            explanation=explanation,
            confidence=confidence
        )

    def _truncate_to_byte_limit(self, text: str, max_bytes: int) -> str:
        """
        Truncate text to fit within a byte limit (UTF-8 encoding).
        
        This method ensures we don't cut in the middle of a multi-byte character.
        
        Args:
            text: Text to truncate
            max_bytes: Maximum number of UTF-8 bytes allowed
            
        Returns:
            Truncated text that fits within the byte limit
        """
        if not text:
            return ""
        
        # If text is already within limit, return as-is
        encoded = text.encode('utf-8')
        if len(encoded) <= max_bytes:
            return text
        
        # Truncate byte by byte, ensuring we don't break multi-byte characters
        truncated = encoded[:max_bytes]
        
        # Decode, ignoring any incomplete multi-byte characters at the end
        try:
            return truncated.decode('utf-8', errors='ignore')
        except Exception as e:
            logging.error(f"Error decoding truncated text: {e}")
            # Fallback: try progressively shorter truncations
            for i in range(max_bytes - 1, max(0, max_bytes - 4), -1):
                try:
                    return encoded[:i].decode('utf-8')
                except:
                    continue
            return ""

    def _detect_sentiment(self, text: str) -> tuple[str, Dict[str, float]]:
        """
        Call AWS Comprehend to detect sentiment.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (sentiment_label, sentiment_scores_dict)
            
        Raises:
            Exception: If AWS Comprehend API call fails
        """
        if not text or not text.strip():
            logging.warning("Empty text provided for sentiment detection")
            return "NEUTRAL", {
                "Positive": 0.0,
                "Negative": 0.0,
                "Neutral": 1.0,
                "Mixed": 0.0
            }
        
        try:
            response = self.comprehend_client.detect_sentiment(
                Text=text,
                LanguageCode='en'
            )
            
            sentiment = response['Sentiment']
            sentiment_scores = response['SentimentScore']
            
            logging.info(f"Detected sentiment: {sentiment}")
            logging.debug(f"Sentiment scores: {sentiment_scores}")
            
            return sentiment, sentiment_scores
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logging.error(f"AWS Comprehend API error ({error_code}): {error_message}")
            raise Exception(f"Failed to detect sentiment: {error_message}")
        except Exception as e:
            logging.error(f"Unexpected error calling AWS Comprehend: {e}")
            raise

    def _format_explanation(self, sentiment: str, scores: Dict[str, float], original_byte_length: int) -> str:
        """
        Format a human-readable explanation of the sentiment result.
        
        Args:
            sentiment: Detected sentiment label
            scores: Dictionary of confidence scores for each sentiment
            original_byte_length: Original text length in bytes
            
        Returns:
            Formatted explanation string
        """
        # Format confidence scores as percentages
        score_lines = []
        for label, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            percentage = score * 100
            score_lines.append(f"{label}: {percentage:.1f}%")
        
        explanation = f"Sentiment: {sentiment}\n"
        explanation += "Confidence scores:\n"
        explanation += "\n".join(f"  - {line}" for line in score_lines)
        
        # Add truncation notice if text was truncated
        if original_byte_length > self.max_bytes:
            explanation += f"\n\nNote: Text was truncated from {original_byte_length} bytes to {self.max_bytes} bytes for analysis."
        
        return explanation

    def register_model(self):
        """
        Register the model with MLflow by logging relevant parameters.
        
        AWS Comprehend is a managed service, so there's no model to register.
        """
        pass

    def save_model(self):
        """
        Save the model to a specified path and log it as an artifact with MLflow.
        
        AWS Comprehend is a managed service, so there's no model to save.
        """
        pass

    def train_model(self):
        """
        Placeholder method to satisfy the base class requirement.
        
        AWS Comprehend is a pre-trained managed service that doesn't require training.
        """
        pass

    def predict_validation(self):
        """
        Placeholder method to satisfy the base class requirement.
        
        This score doesn't require traditional validation since it uses
        AWS Comprehend's pre-trained models.
        """
        pass

