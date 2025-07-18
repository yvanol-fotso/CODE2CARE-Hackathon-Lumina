import os
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pandas as pd
from openpyxl import load_workbook
import re
import json

from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest, InternalServerError
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

# Initialize Flask application
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """Professional sentiment analysis system for healthcare feedback"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.1,
            google_api_key=api_key
        )
        
        # Sentiment mapping for stickers/emojis
        self.sticker_sentiment_map = {
            '😊': 'positive', '😄': 'positive', '👍': 'positive', '❤️': 'positive',
            '😢': 'negative', '😠': 'negative', '😡': 'negative', '👎': 'negative',
            '😐': 'neutral', '🤔': 'neutral', '😕': 'slightly_negative',
            '⭐': 'positive', '🌟': 'positive', '💯': 'positive'
        }
        
        # Healthcare-specific sentiment indicators
        self.healthcare_positive_indicators = [
            'professional', 'excellent', 'caring', 'efficient', 'clean',
            'helpful', 'quick', 'skilled', 'compassionate', 'thorough'
        ]
        
        self.healthcare_negative_indicators = [
            'slow', 'rude', 'unprofessional', 'dirty', 'long wait',
            'poor service', 'incompetent', 'rushed', 'dismissive'
        ]
    
    def extract_sticker_sentiment(self, feedback_text: str) -> Dict:
        """Extract sentiment from stickers/emojis"""
        if not feedback_text:
            return {'sticker_sentiment': 'neutral', 'stickers_found': []}
        
        stickers_found = []
        sentiment_scores = {'positive': 0, 'negative': 0, 'neutral': 0}
        
        for sticker, sentiment in self.sticker_sentiment_map.items():
            if sticker in feedback_text:
                stickers_found.append(sticker)
                sentiment_scores[sentiment] += 1
        
        # Determine overall sticker sentiment
        if sentiment_scores['positive'] > sentiment_scores['negative']:
            sticker_sentiment = 'positive'
        elif sentiment_scores['negative'] > sentiment_scores['positive']:
            sticker_sentiment = 'negative'
        else:
            sticker_sentiment = 'neutral'
        
        return {
            'sticker_sentiment': sticker_sentiment,
            'stickers_found': stickers_found,
            'sentiment_scores': sentiment_scores
        }
    
    def analyze_feedback_sentiment(self, feedback_data: Dict) -> Dict:
        """Comprehensive sentiment analysis for healthcare feedback"""
        
        feedback_text = feedback_data.get('feedback_text', '')
        patient_age = feedback_data.get('patient_age', 'unknown')
        department = feedback_data.get('department', 'unknown')
        wait_time = feedback_data.get('wait_time_min', 0)
        resolution_time = feedback_data.get('resolution_time_min', 0)
        rating = feedback_data.get('rating', 0)
        
        # Extract sticker sentiment
        sticker_analysis = self.extract_sticker_sentiment(feedback_text)
        
        # Prepare context for AI analysis
        context_prompt = f"""
        HEALTHCARE FEEDBACK SENTIMENT ANALYSIS

        You are a professional sentiment analysis expert specializing in healthcare feedback.
        Analyze the following patient feedback with deep contextual understanding.

        FEEDBACK DATA:
        - Text: "{feedback_text}"
        - Patient Age: {patient_age}
        - Department: {department}
        - Wait Time: {wait_time} minutes
        - Resolution Time: {resolution_time} minutes
        - Rating: {rating}/5
        - Stickers Found: {sticker_analysis['stickers_found']}
        - Sticker Sentiment: {sticker_analysis['sticker_sentiment']}

        ANALYSIS REQUIREMENTS:
        1. PRIMARY SENTIMENT: Classify as positive, negative, neutral, or mixed
        2. CONFIDENCE SCORE: Rate confidence 0-100%
        3. EMOTIONAL INTENSITY: Rate 1-10 (1=mild, 10=extreme)
        4. KEY THEMES: Identify main concerns/praises
        5. CONTEXTUAL FACTORS: Consider age, department, wait times
        6. PATIENT BEHAVIOR ANALYSIS: Explain customer behavior patterns
        7. ACTIONABLE INSIGHTS: Provide specific recommendations
        8. URGENCY LEVEL: Rate 1-5 (1=low, 5=critical)

        HEALTHCARE CONTEXT KNOWLEDGE:
        - Emergency department: Higher tolerance for wait times but expect urgency
        - Pediatrics: Parents more emotional, protective language
        - Oncology: Patients more sensitive, need compassionate care
        - Outpatient: Expect efficiency and convenience
        - Cardiology: Patients often anxious, need reassurance
        - Radiology: Expect quick, professional service

        PATIENT BEHAVIOR PATTERNS:
        - Elderly patients (65+): Value personal attention, may express concerns about technology
        - Young adults (18-35): Expect digital convenience, quick service
        - Middle-aged (36-64): Balance efficiency with thoroughness
        - Parents with children: Protective, emotional responses

        WAIT TIME IMPACT:
        - <15 minutes: Generally acceptable
        - 15-30 minutes: Moderate concern
        - 30-60 minutes: Significant frustration
        - >60 minutes: High negative impact
-  Respond to the user in the language he use to query you
        Provide your analysis in the following JSON format:
        {{
            "primary_sentiment": "positive|negative|neutral|mixed",
            "confidence_score": 85,
            "emotional_intensity": 7,
            "key_themes": ["theme1", "theme2"],
            "contextual_factors": "explanation",
            "patient_behavior_analysis": "detailed explanation",
            "actionable_insights": ["insight1", "insight2"],
            "urgency_level": 3,
            "sentiment_explanation": "detailed explanation",
            "department_specific_insights": "department-specific analysis"
        }}
        """
        
        try:
            response = self.model.invoke(context_prompt)
            
            # Parse AI response
            ai_analysis = self._parse_ai_response(response.content)
            
            # Combine all analysis
            comprehensive_analysis = {
                'feedback_id': feedback_data.get('feedback_id', ''),
                'patient_id': feedback_data.get('patient_id', ''),
                'analysis_timestamp': datetime.now().isoformat(),
                'sticker_analysis': sticker_analysis,
                'ai_analysis': ai_analysis,
                'contextual_data': {
                    'patient_age': patient_age,
                    'department': department,
                    'wait_time_min': wait_time,
                    'resolution_time_min': resolution_time,
                    'rating': rating
                },
                'risk_factors': self._assess_risk_factors(feedback_data, ai_analysis),
                'recommendations': self._generate_recommendations(feedback_data, ai_analysis)
            }
            
            return comprehensive_analysis
            
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {str(e)}")
            return self._fallback_analysis(feedback_data, sticker_analysis)
    
    def _parse_ai_response(self, response_text: str) -> Dict:
        """Parse AI response into structured format"""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")
        except:
            # Fallback parsing
            return {
                'primary_sentiment': 'neutral',
                'confidence_score': 50,
                'emotional_intensity': 5,
                'key_themes': ['general_feedback'],
                'contextual_factors': 'Unable to parse detailed analysis',
                'patient_behavior_analysis': 'Standard patient feedback pattern',
                'actionable_insights': ['Review feedback manually'],
                'urgency_level': 2,
                'sentiment_explanation': 'Automated analysis failed, manual review needed',
                'department_specific_insights': 'Standard department protocols apply'
            }
    
    def _assess_risk_factors(self, feedback_data: Dict, ai_analysis: Dict) -> Dict:
        """Assess risk factors for escalation"""
        risk_score = 0
        risk_factors = []
        
        # High wait time
        wait_time = feedback_data.get('wait_time_min', 0)
        if wait_time > 60:
            risk_score += 3
            risk_factors.append('excessive_wait_time')
        
        # Low rating
        rating = feedback_data.get('rating', 5)
        if rating <= 2:
            risk_score += 4
            risk_factors.append('low_rating')
        
        # Negative sentiment
        if ai_analysis.get('primary_sentiment') == 'negative':
            risk_score += 2
            risk_factors.append('negative_sentiment')
        
        # High emotional intensity
        if ai_analysis.get('emotional_intensity', 0) >= 8:
            risk_score += 3
            risk_factors.append('high_emotional_intensity')
        
        # Emergency department negative feedback
        if feedback_data.get('department') == 'Emergency' and ai_analysis.get('primary_sentiment') == 'negative':
            risk_score += 2
            risk_factors.append('emergency_negative_feedback')
        
        return {
            'risk_score': min(risk_score, 10),
            'risk_level': 'high' if risk_score >= 7 else 'medium' if risk_score >= 4 else 'low',
            'risk_factors': risk_factors
        }
    
    def _generate_recommendations(self, feedback_data: Dict, ai_analysis: Dict) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        department = feedback_data.get('department', '')
        sentiment = ai_analysis.get('primary_sentiment', 'neutral')
        wait_time = feedback_data.get('wait_time_min', 0)
        
        # Wait time recommendations
        if wait_time > 45:
            recommendations.append(f"Address wait time concerns in {department}")
            recommendations.append("Implement better patient communication about delays")
        
        # Sentiment-based recommendations
        if sentiment == 'negative':
            recommendations.append("Schedule follow-up contact with patient")
            recommendations.append("Review staff training needs")
        elif sentiment == 'positive':
            recommendations.append("Share positive feedback with staff")
            recommendations.append("Identify best practices to replicate")
        
        # Department-specific recommendations
        if department == 'Emergency':
            recommendations.append("Review triage process efficiency")
        elif department == 'Pediatrics':
            recommendations.append("Enhance child-friendly environment")
        elif department == 'Oncology':
            recommendations.append("Ensure compassionate care protocols")
        
        return recommendations
    
    def _fallback_analysis(self, feedback_data: Dict, sticker_analysis: Dict) -> Dict:
        """Fallback analysis when AI fails"""
        return {
            'feedback_id': feedback_data.get('feedback_id', ''),
            'patient_id': feedback_data.get('patient_id', ''),
            'analysis_timestamp': datetime.now().isoformat(),
            'sticker_analysis': sticker_analysis,
            'ai_analysis': {
                'primary_sentiment': 'neutral',
                'confidence_score': 30,
                'emotional_intensity': 5,
                'key_themes': ['general_feedback'],
                'contextual_factors': 'Automated analysis unavailable',
                'patient_behavior_analysis': 'Standard patient feedback',
                'actionable_insights': ['Manual review required'],
                'urgency_level': 2,
                'sentiment_explanation': 'Fallback analysis used',
                'department_specific_insights': 'Standard protocols apply'
            },
            'contextual_data': {
                'patient_age': feedback_data.get('patient_age', 'unknown'),
                'department': feedback_data.get('department', 'unknown'),
                'wait_time_min': feedback_data.get('wait_time_min', 0),
                'resolution_time_min': feedback_data.get('resolution_time_min', 0),
                'rating': feedback_data.get('rating', 0)
            },
            'risk_factors': {'risk_score': 2, 'risk_level': 'low', 'risk_factors': ['manual_review_needed']},
            'recommendations': ['Manual sentiment analysis required']
        }

class PDFRAGService:
    """Enhanced RAG service with sentiment analysis integration"""
    def __init__(self, api_key: str, pdf_directory: str = "pdfs", excel_directory: str = "excel_files"):
        self.api_key = api_key
        self.pdf_directory = pdf_directory
        self.excel_directory = excel_directory
        self.vector_store = None
        self.embeddings = None
        self.chain = None
        self.pdf_metadata = {}
        self.excel_metadata = {}
    
        # Initialize sentiment analyzer
        self.sentiment_analyzer = SentimentAnalyzer(api_key)
    
        # Initialize components
        self._initialize_embeddings()
        self._load_or_create_vector_store()
        self._initialize_chain()

    def _initialize_embeddings(self):
        """Initialize Google AI embeddings"""
        try:
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model="models/embedding-001", 
                google_api_key=self.api_key
            )
            logger.info("Embeddings initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {str(e)}")
            raise
    
    def _extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from a single PDF file"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text
                return text
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {str(e)}")
            return ""
    
    def _extract_excel_text(self, excel_path: str) -> str:
        """Extract text from all sheets of an Excel file"""
        try:
            excel_file = pd.ExcelFile(excel_path)
            combined_text = ""
            sheet_info = {}
            
            for sheet_name in excel_file.sheet_names:
                try:
                    df = pd.read_excel(excel_path, sheet_name=sheet_name)
                    sheet_text = f"\n=== SHEET: {sheet_name} ===\n"
                    
                    if not df.empty:
                        sheet_text += f"Columns: {', '.join(df.columns.tolist())}\n"
                        sheet_text += f"Row count: {len(df)}\n\n"
                        
                        for index, row in df.iterrows():
                            row_text = f"Row {index + 1}: "
                            for col_name, value in row.items():
                                if pd.notna(value):
                                    row_text += f"{col_name}: {value}, "
                            sheet_text += row_text.rstrip(", ") + "\n"
                    
                    combined_text += sheet_text + "\n"
                    
                    sheet_info[sheet_name] = {
                        'rows': len(df),
                        'columns': df.columns.tolist(),
                        'non_empty_cells': df.count().sum()
                    }
                    
                except Exception as e:
                    logger.warning(f"Error reading sheet {sheet_name}: {str(e)}")
                    continue
            
            filename = os.path.basename(excel_path)
            self.excel_metadata[filename] = {
                'path': excel_path,
                'sheets': sheet_info,
                'total_sheets': len(sheet_info),
                'processed_at': datetime.now().isoformat()
            }
            
            return combined_text
            
        except Exception as e:
            logger.error(f"Error extracting Excel text from {excel_path}: {str(e)}")
            return ""
    
    def _get_text_chunks(self, text: str, source_type: str = "pdf") -> List[str]:
        """Split text into chunks for processing"""
        if source_type == "excel":
            chunk_size = 8000
            chunk_overlap = 500
        else:
            chunk_size = 10000
            chunk_overlap = 1000
            
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, 
            chunk_overlap=chunk_overlap
        )
        return text_splitter.split_text(text)
    
    def _files_changed(self) -> bool:
        """Check if files have been modified since last processing"""
        try:
            current_files = {}
            
            # Check PDF files
            if os.path.exists(self.pdf_directory):
                for file in os.listdir(self.pdf_directory):
                    if file.lower().endswith('.pdf'):
                        file_path = os.path.join(self.pdf_directory, file)
                        try:
                            current_files[file] = {
                                'path': file_path,
                                'modified': os.path.getmtime(file_path),
                                'size': os.path.getsize(file_path)
                            }
                        except (OSError, PermissionError) as e:
                            logger.warning(f"Cannot access file {file_path}: {str(e)}")
                            return True  # Treat inaccessible files as changed
            
            # Check Excel files
            if os.path.exists(self.excel_directory):
                for file in os.listdir(self.excel_directory):
                    if file.lower().endswith(('.xlsx', '.xls')):
                        file_path = os.path.join(self.excel_directory, file)
                        try:
                            current_files[file] = {
                                'path': file_path,
                                'modified': os.path.getmtime(file_path),
                                'size': os.path.getsize(file_path)
                            }
                        except (OSError, PermissionError) as e:
                            logger.warning(f"Cannot access file {file_path}: {str(e)}")
                            return True  # Treat inaccessible files as changed
            
            # Compare with cached metadata
            for file, info in current_files.items():
                cached_info = self.pdf_metadata.get(file, self.excel_metadata.get(file))
                if not cached_info:
                    logger.info(f"New file detected: {file}")
                    return True  # New file found
                
                # Check if file has changed (allow 1-second tolerance for timestamp)
                if (abs(info['modified'] - cached_info.get('last_modified', 0)) > 1.0 or 
                    info['size'] != cached_info.get('file_size', 0)):
                    logger.info(f"File modified: {file}")
                    return True
            
            # Check for deleted files
            all_cached_files = set(self.pdf_metadata.keys()) | set(self.excel_metadata.keys())
            current_file_names = set(current_files.keys())
            if all_cached_files != current_file_names:
                logger.info("File set changed (files added or deleted)")
                return True
            
            logger.info("No file changes detected")
            return False
        
        except Exception as e:
            logger.warning(f"Error checking file changes: {str(e)}. Triggering reprocessing as a precaution.")
            return True
    
    def _load_and_process_files(self):
        """Load all PDFs and Excel files and create vector store"""
        # Ensure directories exist
        for directory in [self.pdf_directory, self.excel_directory]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                logger.info(f"Directory created: {directory}")
        
        pdf_files = [f for f in os.listdir(self.pdf_directory) if f.lower().endswith('.pdf')]
        excel_files = [f for f in os.listdir(self.excel_directory) 
                      if f.lower().endswith(('.xlsx', '.xls'))]
        
        if not pdf_files and not excel_files:
            logger.warning("No PDF or Excel files found")
            self.vector_store = None
            return
        
        logger.info(f"Found {len(pdf_files)} PDF files and {len(excel_files)} Excel files")
        
        all_chunks = []
        chunk_metadata = []
        
        # Process PDF files
        for pdf_file in pdf_files:
            pdf_path = os.path.join(self.pdf_directory, pdf_file)
            logger.info(f"Processing PDF: {pdf_file}")
            
            try:
                text = self._extract_pdf_text(pdf_path)
                if text:
                    chunks = self._get_text_chunks(text, "pdf")
                    all_chunks.extend(chunks)
                    
                    self.pdf_metadata[pdf_file] = {
                        'path': pdf_path,
                        'chunk_count': len(chunks),
                        'source_type': 'pdf',
                        'processed_at': datetime.now().isoformat(),
                        'last_modified': os.path.getmtime(pdf_path),
                        'file_size': os.path.getsize(pdf_path)
                    }
                    
                    for i, chunk in enumerate(chunks):
                        chunk_metadata.append({
                            'source': pdf_file,
                            'source_type': 'pdf',
                            'chunk_id': i,
                            'text_preview': chunk[:100] + "..." if len(chunk) > 100 else chunk
                        })
                else:
                    logger.warning(f"No text extracted from {pdf_file}")
            except Exception as e:
                logger.error(f"Error processing PDF {pdf_file}: {str(e)}")
                continue
        
        # Process Excel files
        for excel_file in excel_files:
            excel_path = os.path.join(self.excel_directory, excel_file)
            logger.info(f"Processing Excel file: {excel_file}")
            
            try:
                text = self._extract_excel_text(excel_path)
                if text:
                    chunks = self._get_text_chunks(text, "excel")
                    all_chunks.extend(chunks)
                    
                    self.excel_metadata[excel_file]['chunk_count'] = len(chunks)
                    self.excel_metadata[excel_file]['source_type'] = 'excel'
                    self.excel_metadata[excel_file]['last_modified'] = os.path.getmtime(excel_path)
                    self.excel_metadata[excel_file]['file_size'] = os.path.getsize(excel_path)
                    
                    for i, chunk in enumerate(chunks):
                        chunk_metadata.append({
                            'source': excel_file,
                            'source_type': 'excel',
                            'chunk_id': i,
                            'text_preview': chunk[:100] + "..." if len(chunk) > 100 else chunk
                        })
                else:
                    logger.warning(f"No text extracted from {excel_file}")
            except Exception as e:
                logger.error(f"Error processing Excel {excel_file}: {str(e)}")
                continue
        
        if all_chunks:
            try:
                self.vector_store = FAISS.from_texts(
                    all_chunks, 
                    embedding=self.embeddings,
                    metadatas=chunk_metadata
                )
                
                vector_store_path = "faiss_index_api"
                self.vector_store.save_local(vector_store_path)
                logger.info(f"Vector store saved to {vector_store_path}")
                
                # Save metadata
                self._save_metadata()
                
                logger.info(f"Vector store created with {len(all_chunks)} chunks")
                logger.info(f"Sources: {len(self.pdf_metadata)} PDFs, {len(self.excel_metadata)} Excel files")
                
            except Exception as e:
                logger.error(f"Failed to create vector store: {str(e)}")
                self.vector_store = None
                raise
        else:
            logger.error("No valid text extracted from files")
            self.vector_store = None
            raise ValueError("No valid content found")
    
    def _save_metadata(self):
        """Save metadata to file for caching"""
        try:
            # Remove stale metadata entries
            for file in list(self.pdf_metadata.keys()):
                file_path = self.pdf_metadata[file]['path']
                if not os.path.exists(file_path):
                    logger.info(f"Removing stale metadata for {file}")
                    del self.pdf_metadata[file]
            
            for file in list(self.excel_metadata.keys()):
                file_path = self.excel_metadata[file]['path']
                if not os.path.exists(file_path):
                    logger.info(f"Removing stale metadata for {file}")
                    del self.excel_metadata[file]
            
            # Update metadata with file info
            for file, meta in self.pdf_metadata.items():
                file_path = meta['path']
                if os.path.exists(file_path):
                    meta['last_modified'] = os.path.getmtime(file_path)
                    meta['file_size'] = os.path.getsize(file_path)
            
            for file, meta in self.excel_metadata.items():
                file_path = meta['path']
                if os.path.exists(file_path):
                    meta['last_modified'] = os.path.getmtime(file_path)
                    meta['file_size'] = os.path.getsize(file_path)
            
            metadata = {
                'pdf_metadata': self.pdf_metadata,
                'excel_metadata': self.excel_metadata,
                'last_updated': datetime.now().isoformat()
            }
            
            metadata_path = "processed_files_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Metadata saved to {metadata_path}")
        
        except Exception as e:
            logger.warning(f"Error saving metadata: {str(e)}. Continuing without metadata update.")
    
    def _validate_vector_store(self) -> bool:
        """Validate if the current vector store is usable"""
        if self.vector_store is None:
            return False
        try:
            # Perform a test query to ensure the vector store is functional
            self.vector_store.similarity_search("test query", k=1)
            return True
        except Exception as e:
            logger.warning(f"Vector store validation failed: {str(e)}")
            return False
    
    def _load_or_create_vector_store(self):
        """Load existing vector store or create new one if needed"""
        vector_store_path = "faiss_index_api"
        metadata_path = "processed_files_metadata.json"
        
        # Initialize metadata if empty
        self.pdf_metadata = self.pdf_metadata or {}
        self.excel_metadata = self.excel_metadata or {}
        
        # Check if vector store and metadata exist
        if os.path.exists(vector_store_path) and os.path.exists(metadata_path):
            try:
                # Load existing vector store
                self.vector_store = FAISS.load_local(
                    vector_store_path, 
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info("Loaded existing vector store from cache")
                
                # Load metadata
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        self.pdf_metadata = metadata.get('pdf_metadata', {})
                        self.excel_metadata = metadata.get('excel_metadata', {})
                        logger.info("Loaded existing metadata from cache")
                except Exception as e:
                    logger.warning(f"Failed to load metadata: {str(e)}. Reprocessing files.")
                    self._load_and_process_files()
                    return
                
                # Validate vector store
                if self._validate_vector_store():
                    # Check if files have changed
                    if self._files_changed():
                        logger.info("Files have changed, reprocessing...")
                        self._load_and_process_files()
                    else:
                        logger.info("Files unchanged, using cached vector store")
                else:
                    logger.info("Vector store invalid, reprocessing...")
                    self._load_and_process_files()
                
            except Exception as e:
                logger.warning(f"Failed to load cached vector store: {str(e)}. Creating new vector store...")
                self._load_and_process_files()
        else:
            logger.info("No cached vector store or metadata found, creating new one...")
            self._load_and_process_files()
    
    def _initialize_chain(self):
        """Initialize conversational chain with instructions for PDF and Excel"""
        prompt_template = """
        INSTRUCTIONS:
        -You are a hospital customer-insight assistant. Use the provided patient feedback snippets to answer questions precisely. Always cite specific feedback IDs when possible.
        - Answer questions using information from loaded PDF documents and Excel files (employee data)
        - You have access to both PDF documents and Excel data containing employee information
        - For employee-related questions, use Excel data with detailed staff information
        - Respond in the language of the question asked
        - Don't explicitly mention that your sources are PDF documents or Excel files
        - Respond professionally and formally
        - For questions about employees, staff, or human resources, use available Excel data
        - Analyze each question carefully and treat it as a unique new request
        - Provide precise, detailed, and contextualized answers
        - If you don't find relevant information, think of it yourself
        - you should analyse patients feedback and give explanation
        - you've been created by Team Lumina For Douala's General Hospital Hackatoon
        - respond to the user according to the language he use to query to you even if its a local language in cameroon 
        - if user query you in language respond in the language he used example if he query in french respond in french 
        DOCUMENT CONTEXT (PDF and Excel):
        {context}
        
        USER QUESTION:
        {question}
        
        DETAILED RESPONSE:
        Based on the analysis of available information, here is my response:
        """
        
        try:
            model = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash", 
                temperature=0.2,
                google_api_key=self.api_key
            )
            
            prompt = PromptTemplate(
                template=prompt_template, 
                input_variables=["context", "question"]
            )
            
            self.chain = load_qa_chain(model, chain_type="stuff", prompt=prompt)
            logger.info("Conversational chain initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize chain: {str(e)}")
            raise
    
    def query(self, question: str) -> Dict:
        """Process a query and return a fresh response"""
        if not question or not question.strip():
            raise BadRequest("Question cannot be empty")
        
        if not self.vector_store or not self.chain:
            raise InternalServerError("RAG system not properly initialized")
        
        try:
            docs = self.vector_store.similarity_search(question, k=4)
            
            logger.info(f"Processing new query: {question[:100]}...")
            logger.info(f"Number of documents found: {len(docs)}")
            
            response = self.chain(
                {"input_documents": docs, "question": question}, 
                return_only_outputs=True
            )
            
            pdf_sources = []
            excel_sources = []
            
            for doc in docs:
                if hasattr(doc, 'metadata'):
                    source_type = doc.metadata.get('source_type', 'unknown')
                    source_name = doc.metadata.get('source', 'unknown')
                    
                    if source_type == 'pdf':
                        pdf_sources.append(source_name)
                    elif source_type == 'excel':
                        excel_sources.append(source_name)
            
            result = {
                "question": question,
                "answer": response['output_text'],
                "timestamp": datetime.now().isoformat(),
                "processing_id": datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
                "sources_used": len(docs),
                "pdf_sources": list(set(pdf_sources)),
                "excel_sources": list(set(excel_sources)),
                "relevant_passages": [
                    {
                        "source": doc.metadata.get('source', 'unknown'),
                        "source_type": doc.metadata.get('source_type', 'unknown'),
                        "preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                    } for doc in docs[:2]
                ]
            }
            
            logger.info(f"Query processed successfully - ID: {result['processing_id']}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            raise InternalServerError(f"Failed to process query: {str(e)}")
    
    def analyze_sentiment(self, feedback_data: Dict) -> Dict:
        """Analyze sentiment of feedback data"""
        try:
            return self.sentiment_analyzer.analyze_feedback_sentiment(feedback_data)
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {str(e)}")
            raise InternalServerError(f"Failed to analyze sentiment: {str(e)}")
    
    def get_system_info(self) -> Dict:
        """Get information about loaded files and system status"""
        return {
            "status": "active",
            "cache_status": "enabled" if self.vector_store and not self._files_changed() else "reprocessing required",
            "pdfs_loaded": len(self.pdf_metadata),
            "excel_files_loaded": len(self.excel_metadata),
            "pdf_files": list(self.pdf_metadata.keys()),
            "excel_files": list(self.excel_metadata.keys()),
            "pdf_details": self.pdf_metadata,
            "excel_details": self.excel_metadata,
            "vector_store_ready": self.vector_store is not None,
            "chain_ready": self.chain is not None,
            "sentiment_analyzer_ready": self.sentiment_analyzer is not None,
            "last_check": datetime.now().isoformat()
        }

class WhatsAppService:
    """Service to handle WhatsApp messages with Twilio"""
    
    def __init__(self, account_sid: str, auth_token: str, whatsapp_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.whatsapp_number = whatsapp_number
        self.client = Client(account_sid, auth_token)
        
        logger.info("WhatsApp service initialized successfully")
    
    def send_message(self, to_number: str, message: str, media_url: Optional[str] = None) -> Dict:
        """Send a WhatsApp message"""
        try:
            if not to_number.startswith('whatsapp:'):
                to_number = f'whatsapp:{to_number}'
            
            message_params = {
                'body': message,
                'from_': f'whatsapp:{self.whatsapp_number}',
                'to': to_number
            }
            
            if media_url:
                message_params['media_url'] = [media_url]
            
            message_obj = self.client.messages.create(**message_params)
            
            result = {
                'success': True,
                'message_sid': message_obj.sid,
                'to': to_number,
                'status': message_obj.status,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"WhatsApp message sent successfully - SID: {message_obj.sid}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_message_status(self, message_sid: str) -> Dict:
        """Get message status"""
        try:
            message = self.client.messages(message_sid).fetch()
            return {
                'sid': message.sid,
                'status': message.status,
                'to': message.to,
                'from': message.from_,
                'body': message.body,
                'date_created': message.date_created.isoformat() if message.date_created else None,
                'date_updated': message.date_updated.isoformat() if message.date_updated else None,
                'error_code': message.error_code,
                'error_message': message.error_message
            }
        except Exception as e:
            logger.error(f"Error retrieving message status: {str(e)}")
            return {'error': str(e)}

def initialize_services():
    """Initialize all services at startup"""
    global rag_service, whatsapp_service
    
    google_api_key = os.getenv('GOOGLE_API_KEY')
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    
    pdf_directory = os.getenv('PDF_DIRECTORY', 'pdfs')
    excel_directory = os.getenv('EXCEL_DIRECTORY', 'excel_files')
    
    # Check if RAG service is already initialized and valid
    if rag_service and rag_service.vector_store and rag_service.chain:
        try:
            system_info = rag_service.get_system_info()
            if system_info['vector_store_ready'] and system_info['chain_ready'] and not rag_service._files_changed():
                logger.info("Existing RAG service is valid and files unchanged, skipping reinitialization")
                return
        except Exception as e:
            logger.warning(f"Existing RAG service invalid or files changed: {str(e)}. Reinitializing...")
    
    try:
        rag_service = PDFRAGService(google_api_key, pdf_directory, excel_directory)
        logger.info("RAG service with Excel support initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {str(e)}")
        raise
    
    twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    twilio_whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')
    
    if twilio_account_sid and twilio_auth_token and twilio_whatsapp_number:
        try:
            whatsapp_service = WhatsAppService(
                twilio_account_sid, 
                twilio_auth_token, 
                twilio_whatsapp_number
            )
            logger.info("WhatsApp service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WhatsApp service: {str(e)}")
            whatsapp_service = None
    else:
        logger.warning("WhatsApp service not configured - missing Twilio credentials")
        whatsapp_service = None

# Initialize services
load_dotenv()
rag_service = None
whatsapp_service = None

# API Routes
@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "PDF RAG API with Excel Support & Sentiment Analysis",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    })

@app.route('/api/query', methods=['POST'])
def query_documents():
    """Query documents endpoint"""
    try:
        if not rag_service:
            return jsonify({"error": "RAG service not initialized"}), 500
        
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({"error": "Question is required"}), 400
        
        question = data['question'].strip()
        if not question:
            return jsonify({"error": "Question cannot be empty"}), 400
        
        result = rag_service.query(question)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except BadRequest as e:
        return jsonify({"error": str(e)}), 400
    except InternalServerError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error in query endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/sentiment', methods=['POST'])
def analyze_sentiment():
    """Sentiment analysis endpoint"""
    try:
        if not rag_service:
            return jsonify({"error": "RAG service not initialized"}), 500
        
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Feedback data is required"}), 400
        
        # Validate required fields
        required_fields = ['feedback_text']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Set default values for optional fields
        feedback_data = {
            'feedback_id': data.get('feedback_id', f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
            'patient_id': data.get('patient_id', 'anonymous'),
            'feedback_text': data['feedback_text'],
            'patient_age': data.get('patient_age', 'unknown'),
            'department': data.get('department', 'unknown'),
            'wait_time_min': data.get('wait_time_min', 0),
            'resolution_time_min': data.get('resolution_time_min', 0),
            'rating': data.get('rating', 0)
        }
        
        result = rag_service.analyze_sentiment(feedback_data)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except BadRequest as e:
        return jsonify({"error": str(e)}), 400
    except InternalServerError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error in sentiment endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/whatsapp/send', methods=['POST'])
def send_whatsapp():
    """Send WhatsApp message endpoint"""
    try:
        if not whatsapp_service:
            return jsonify({"error": "WhatsApp service not configured"}), 500
        
        data = request.get_json()
        
        if not data or 'to' not in data or 'message' not in data:
            return jsonify({"error": "Missing required fields: 'to' and 'message'"}), 400
        
        to_number = data['to']
        message = data['message']
        media_url = data.get('media_url')
        
        result = whatsapp_service.send_message(to_number, message, media_url)
        
        return jsonify({
            "success": result['success'],
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Error in WhatsApp send endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    """WhatsApp webhook endpoint"""
    try:
        incoming_msg = request.values.get('Body', '').strip()
        from_number = request.values.get('From', '')
        
        logger.info(f"Received WhatsApp message from {from_number}: {incoming_msg}")
        
        # Create TwiML response
        resp = MessagingResponse()
        msg = resp.message()
        
        if not rag_service:
            msg.body("Service temporarily unavailable. Please try again later.")
            return str(resp)
        
        # Process the message as a query
        if incoming_msg:
            try:
                result = rag_service.query(incoming_msg)
                response_text = result['answer']
                
                # Truncate response if too long for WhatsApp
                if len(response_text) > 1500:
                    response_text = response_text[:1500] + "...\n\nFor more details, please contact us directly."
                
                msg.body(response_text)
                
            except Exception as e:
                logger.error(f"Error processing WhatsApp query: {str(e)}")
                msg.body("Sorry, I couldn't process your request. Please try again or contact support.")
        else:
            msg.body("Hello! I'm your AI assistant. Ask me anything about our services.")
        
        return str(resp)
        
    except Exception as e:
        logger.error(f"Error in WhatsApp webhook: {str(e)}")
        resp = MessagingResponse()
        msg = resp.message()
        msg.body("Sorry, there was an error processing your message.")
        return str(resp)

@app.route('/api/whatsapp/status/<message_sid>', methods=['GET'])
def get_whatsapp_status(message_sid):
    """Get WhatsApp message status"""
    try:
        if not whatsapp_service:
            return jsonify({"error": "WhatsApp service not configured"}), 500
        
        result = whatsapp_service.get_message_status(message_sid)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Error getting WhatsApp status: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/system/info', methods=['GET'])
def get_system_info():
    """Get system information"""
    try:
        if not rag_service:
            return jsonify({"error": "RAG service not initialized"}), 500
        
        info = rag_service.get_system_info()
        
        # Add WhatsApp service status
        info['whatsapp_service_ready'] = whatsapp_service is not None
        
        return jsonify({
            "success": True,
            "data": info
        })
        
    except Exception as e:
        logger.error(f"Error getting system info: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/system/reload', methods=['POST'])
def reload_system():
    """Reload the system (reinitialize services)"""
    try:
        global rag_service, whatsapp_service
        
        # Reinitialize services
        initialize_services()
        
        return jsonify({
            "success": True,
            "message": "System reloaded successfully",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error reloading system: {str(e)}")
        return jsonify({"error": f"Failed to reload system: {str(e)}"}), 500

@app.route('/api/files/upload', methods=['POST'])
def upload_file():
    """Upload PDF or Excel file"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if not file.filename.lower().endswith(('.pdf', '.xlsx', '.xls')):
            return jsonify({"error": "Only PDF and Excel files are allowed"}), 400
        
        # Determine directory based on file type
        if file.filename.lower().endswith('.pdf'):
            directory = os.getenv('PDF_DIRECTORY', 'pdfs')
        else:
            directory = os.getenv('EXCEL_DIRECTORY', 'excel_files')
        
        # Ensure directory exists
        os.makedirs(directory, exist_ok=True)
        
        # Save file
        file_path = os.path.join(directory, file.filename)
        file.save(file_path)
        
        logger.info(f"File uploaded: {file_path}")
        
        # Trigger reload to process new file
        initialize_services()
        
        return jsonify({
            "success": True,
            "message": f"File uploaded and processed successfully: {file.filename}",
            "file_path": file_path
        })
        
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return jsonify({"error": "File upload failed"}), 500

@app.route('/api/files/list', methods=['GET'])
def list_files():
    """List all uploaded files"""
    try:
        pdf_directory = os.getenv('PDF_DIRECTORY', 'pdfs')
        excel_directory = os.getenv('EXCEL_DIRECTORY', 'excel_files')
        
        files = {
            'pdf_files': [],
            'excel_files': []
        }
        
        # List PDF files
        if os.path.exists(pdf_directory):
            pdf_files = [f for f in os.listdir(pdf_directory) if f.lower().endswith('.pdf')]
            for pdf_file in pdf_files:
                file_path = os.path.join(pdf_directory, pdf_file)
                try:
                    files['pdf_files'].append({
                        'name': pdf_file,
                        'path': file_path,
                        'size': os.path.getsize(file_path),
                        'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                    })
                except (OSError, PermissionError) as e:
                    logger.warning(f"Cannot access PDF file {file_path}: {str(e)}")
                    continue
        
        # List Excel files
        if os.path.exists(excel_directory):
            excel_files = [f for f in os.listdir(excel_directory) if f.lower().endswith(('.xlsx', '.xls'))]
            for excel_file in excel_files:
                file_path = os.path.join(excel_directory, excel_file)
                try:
                    files['excel_files'].append({
                        'name': excel_file,
                        'path': file_path,
                        'size': os.path.getsize(file_path),
                        'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                    })
                except (OSError, PermissionError) as e:
                    logger.warning(f"Cannot access Excel file {file_path}: {str(e)}")
                    continue
        
        return jsonify({
            "success": True,
            "data": files
        })
        
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return jsonify({"error": "Failed to list files"}), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors"""
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    try:
        # Initialize services at startup
        initialize_services()
        
        # Get configuration from environment
        host = os.getenv('FLASK_HOST', '0.0.0.0')
        port = int(os.getenv('FLASK_PORT', 5000))
        debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        
        logger.info(f"Starting Flask application on {host}:{port}")
        logger.info(f"Debug mode: {debug}")
        
        app.run(host=host, port=port, debug=debug)
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise