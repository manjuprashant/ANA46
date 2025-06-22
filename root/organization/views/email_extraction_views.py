import requests
from django.conf import settings
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from organization.serializers.email_extraction_serializers import (
    StartEmailExtractionSerializer,
    EmailExtractionStatusSerializer,
    EmailExtractionResultSerializer,
    StartBatchEmailExtractionSerializer,
    BatchEmailExtractionStatusSerializer,
    BatchEmailExtractionResultSerializer,
    PauseEmailExtractionSerializer,
    ContinueEmailExtractionSerializer,
    CancelEmailExtractionSerializer,
    PauseBatchEmailExtractionSerializer,
    ContinueBatchEmailExtractionSerializer,
    CancelBatchEmailExtractionSerializer
)
from drf_yasg.utils import swagger_auto_schema

FLASK_BASE_URL = "http://127.0.0.1:3006/api/emails/extract"

class StartEmailExtractionView(APIView):
    @swagger_auto_schema(request_body=StartEmailExtractionSerializer)
    def post(self, request, connection_id):
        serializer = StartEmailExtractionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flask_url = f"{FLASK_BASE_URL}/start/{connection_id}"
        response = requests.post(flask_url, json=serializer.validated_data)
        return JsonResponse(response.json(), status=response.status_code)

class EmailExtractionStatusView(APIView):
    @swagger_auto_schema(responses={200: EmailExtractionStatusSerializer})
    def get(self, request, connection_id):
        flask_url = f"{FLASK_BASE_URL}/status/{connection_id}"
        response = requests.get(flask_url)
        
        if response.status_code == 200:
            serializer = EmailExtractionStatusSerializer(data=response.json())
            serializer.is_valid(raise_exception=True)
            return JsonResponse(serializer.validated_data, status=200)
        
        return JsonResponse(response.json(), status=response.status_code)

class EmailExtractionResultView(APIView):
    @swagger_auto_schema(responses={200: EmailExtractionResultSerializer})
    def get(self, request, connection_id):
        flask_url = f"{FLASK_BASE_URL}/result/{connection_id}"
        response = requests.get(flask_url)
        
        if response.status_code == 200:
            serializer = EmailExtractionResultSerializer(data=response.json())
            serializer.is_valid(raise_exception=True)
            return JsonResponse(serializer.validated_data, status=200)
        
        return JsonResponse(response.json(), status=response.status_code)

class StartBatchEmailExtractionView(APIView):
    @swagger_auto_schema(request_body=StartBatchEmailExtractionSerializer)
    def post(self, request):
        serializer = StartBatchEmailExtractionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        flask_url = f"{FLASK_BASE_URL}/batch/start"
        response = requests.post(flask_url, json=serializer.validated_data)
        return JsonResponse(response.json(), status=response.status_code)

class BatchEmailExtractionStatusView(APIView):
    @swagger_auto_schema(responses={200: BatchEmailExtractionStatusSerializer})
    def get(self, request, batch_id):
        flask_url = f"{FLASK_BASE_URL}/batch/status/{batch_id}"
        response = requests.get(flask_url)
        
        if response.status_code == 200:
            serializer = BatchEmailExtractionStatusSerializer(data=response.json())
            serializer.is_valid(raise_exception=True)
            return JsonResponse(serializer.validated_data, status=200)
        
        return JsonResponse(response.json(), status=response.status_code)

class BatchEmailExtractionResultView(APIView):
    @swagger_auto_schema(responses={200: BatchEmailExtractionResultSerializer})
    def get(self, request, batch_id):
        flask_url = f"{FLASK_BASE_URL}/batch/result/{batch_id}"
        response = requests.get(flask_url)
        
        if response.status_code == 200:
            serializer = BatchEmailExtractionResultSerializer(data=response.json())
            serializer.is_valid(raise_exception=True)
            return JsonResponse(serializer.validated_data, status=200)
        
        return JsonResponse(response.json(), status=response.status_code)

class PauseEmailExtractionView(APIView):
    @swagger_auto_schema(request_body=PauseEmailExtractionSerializer)
    def post(self, request, connection_id):
        flask_url = f"{FLASK_BASE_URL}/pause/{connection_id}"
        response = requests.post(flask_url)
        return JsonResponse(response.json(), status=response.status_code)

class ContinueEmailExtractionView(APIView):
    @swagger_auto_schema(request_body=ContinueEmailExtractionSerializer)
    def post(self, request, connection_id):
        flask_url = f"{FLASK_BASE_URL}/continue/{connection_id}"
        response = requests.post(flask_url)
        return JsonResponse(response.json(), status=response.status_code)

class CancelEmailExtractionView(APIView):
    @swagger_auto_schema(request_body=CancelEmailExtractionSerializer)
    def post(self, request, connection_id):
        flask_url = f"{FLASK_BASE_URL}/cancel/{connection_id}"
        response = requests.post(flask_url)
        return JsonResponse(response.json(), status=response.status_code)

class PauseBatchEmailExtractionView(APIView):
    @swagger_auto_schema(request_body=PauseBatchEmailExtractionSerializer)
    def post(self, request, batch_id):
        flask_url = f"{FLASK_BASE_URL}/batch/pause/{batch_id}"
        response = requests.post(flask_url)
        return JsonResponse(response.json(), status=response.status_code)

class ContinueBatchEmailExtractionView(APIView):
    @swagger_auto_schema(request_body=ContinueBatchEmailExtractionSerializer)
    def post(self, request, batch_id):
        flask_url = f"{FLASK_BASE_URL}/batch/continue/{batch_id}"
        response = requests.post(flask_url)
        return JsonResponse(response.json(), status=response.status_code)

class CancelBatchEmailExtractionView(APIView):
    @swagger_auto_schema(request_body=CancelBatchEmailExtractionSerializer)
    def post(self, request, batch_id):
        flask_url = f"{FLASK_BASE_URL}/batch/cancel/{batch_id}"
        response = requests.post(flask_url)
        return JsonResponse(response.json(), status=response.status_code)