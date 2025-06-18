import asyncio
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from rest_framework.parsers import MultiPartParser
from Gemini_RAG_v0_32 import GeminiRAG
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets, permissions
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from . import serializers
from .models import User, Card, Notification, Comment, SavedCard, CommentLike  # CommentReply, CommentReplyLike,
from .serializers import (
    OTPLoginSerializer, UserSerializer,CardSerializer,
    NotificationSerializer, LoginSerializer, CommentSerializer,
    SavedCardSerializer, MentionUserSerializer, FlatCommentWithMetaSerializer,
    CardDetailSerializer, CommentCreatorIdSerializer, UserProfileImageUpdateSerializer
    # CommentWithRepliesCreatorSerializer, CommentReplySerializer, CommentWithRepliesSerializer,
    #CommentWithRepliesCreatorSerializer,  UserRegistrationSerializer
)
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from .utils import (generate_otp, verify_otp, get_or_create_user, generate_tokens_for_user,
                    extract_mentions, send_otp_sms, ensure_bot_user, upload_image_to_minio
                    )
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import extend_schema, OpenApiParameter
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

# from .gemini_rag import GeminiRAG
# api_key = getattr(settings, "MY_API_KEY", None)
rag = GeminiRAG(api_key="AIzaSyB2jJ1gmhbj05KBuLZY3pJNiS9h-CkDTJ0")


# rag.load_vectorstore()


class OTPLoginView(APIView):
    permission_classes = []  # Allow unauthenticated users

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["کد تایید با موفقیت ارسال شد."]
                    },
                    "total": {"type": "integer", "example": 0},
                    "page": {"type": "integer", "example": 1},
                    "perPage": {"type": "integer", "example": 10},
                    "result": {
                        "type": "object",
                        "properties": {
                            "phoneNumber": {"type": "string", "example": "09123456789"},
                            "username": {"type": "string", "example": "user_example"},
                            "Full_name": {"type": "string", "example": "Full Name"},
                            "dataGathering": {"type": "boolean", "example": True}
                        }
                    }
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Invalid input data."]
                    },
                    "errors": {"type": "object"}
                }
            }
        }
    )
    def post(self, request):
        login_serializer = LoginSerializer(data=request.data)
        if not login_serializer.is_valid():
            return Response({
                "statusCode": 400,
                "messages": ["Invalid input data."],
                "errors": login_serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        mobile_phone_number = login_serializer.validated_data["mobile_phone_number"]
        user, created = User.objects.get_or_create(mobile_phone_number=mobile_phone_number)

        otp = generate_otp()
        cache.set(f"otp:{mobile_phone_number}", otp, timeout=300)

        if not send_otp_sms(mobile_phone_number, otp):
            cache.delete(f"otp:{mobile_phone_number}")
            return Response({
                "statusCode": 500,
                "messages": ["خطا در ارسال کد تایید."],
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "statusCode": 200,
            "messages": ["کد تایید با موفقیت ارسال شد."],
            "total": 0,
            "page": 1,
            "perPage": 10,
            "result": {
                "phoneNumber": mobile_phone_number,
                "username": user.username if user.username else "N/A",
                "Full_name": user.Full_name if user.Full_name else "N/A",
                "dataGathering": True,
                "test": f"OTP: {otp}"
            }
        }, status=status.HTTP_200_OK)


class OTPVerificationView(APIView):
    permission_classes = []  # Allow unauthenticated users

    @extend_schema(
        request=OTPLoginSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "status_code": {"type": "integer", "example": 200},
                    "messagess": {"type": "array", "items": {"type": "string"},
                                  "example": ["OTP verified successfully."]},
                    "access_token": {"type": "string", "example": "generated_access_token"},
                    "refresh_token": {"type": "string", "example": "generated_refresh_token"}
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "status_code": {"type": "integer", "example": 400},
                    "messagess": {"type": "array", "items": {"type": "string"}, "example": ["Invalid OTP data."]},
                    "errors": {"type": "object"}
                }
            }
        }
    )
    def post(self, request):
        serializer = OTPLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "statusCode": 400,
                "messages": ["Invalid OTP data."],
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        mobile_phone_number = serializer.validated_data["mobile_phone_number"]
        submitted_otp = serializer.validated_data["otp"]

        # Verify OTP
        if not verify_otp(mobile_phone_number, submitted_otp):
            return Response({
                "statusCode": 401,
                "messages": ["Invalid or expired OTP."]
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Get or create user
        user = get_or_create_user(mobile_phone_number)

        # Ensure username is set
        if not user.username:
            user.username = f"{user.id} user"
            user.save()

        # Generate tokens
        tokens = generate_tokens_for_user(user)

        # Clear OTP from cache after successful verification
        cache.delete(f"otp:{mobile_phone_number}")

        return Response({
            "statusCode": 200,
            "messages": ["کد کلید با موفقیت ارسال شد."],
            "total": 0,
            "page": 1,
            "perPage": 10,
            "result": {
                "phoneNumber": mobile_phone_number,
                "username": user.username,
                "email": user.email if user.email else "N/A",
                "firstName": user.first_name if user.first_name else "N/A",
                "lastName": user.last_name if user.last_name else "N/A",
                "dataGathering": True,
                "accessToken": tokens["access_token"],
                "refreshToken": tokens["refresh_token"],
            }
        }, status=status.HTTP_200_OK)


class UserProfileView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {"type": "array", "items": {"type": "string"},
                                 "example": ["User profile fetched successfully."]},
                    "total": {"type": "integer", "example": 0},
                    "page": {"type": "integer", "example": 1},
                    "perPage": {"type": "integer", "example": 10},
                    "result": {"type": "object"}
                }
            }
        }
    )
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response({
            "statusCode": 200,
            "messages": ["User profile fetched successfully."],
            "total": 0,
            "page": 1,
            "perPage": 10,
            "result": serializer.data
        }, status=status.HTTP_200_OK)

    @extend_schema(
        request=UserSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {"type": "array", "items": {"type": "string"},
                                 "example": ["Profile updated successfully."]},
                    "total": {"type": "integer", "example": 0},
                    "page": {"type": "integer", "example": 1},
                    "perPage": {"type": "integer", "example": 10},
                    "result": {"type": "object"}
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {"type": "array", "items": {"type": "string"},
                                 "example": ["Failed to update profile."]},
                    "errors": {"type": "object"}
                }
            }
        }
    )
    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "statusCode": 200,
                "messages": ["Profile updated successfully."],
                "total": 0,
                "page": 1,
                "perPage": 10,
                "result": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            "statusCode": 400,
            "messages": ["Failed to update profile."],
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class CustomPagination(PageNumberPagination):
    page_size = 10  # Assuming you want to show 10 cards per page
    page_size_query_param = 'page_size'  # Allow client to set page size
    max_page_size = 100  # Limit the maximum page size


class CardViewSet(viewsets.ModelViewSet):
    queryset = Card.objects.all().order_by('-created_at')
    serializer_class = CardSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def get_permissions(self):
        # Allow unauthenticated access only for the list view.
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return super().get_permissions()

    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Cards retrieved successfully."]
                    },
                    "total": {"type": "integer", "example": 100},
                    "page": {"type": "integer", "example": 1},
                    "perPage": {"type": "integer", "example": 10},
                    "result": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer", "example": 1},
                                "content": {"type": "string", "example": "This is a sample card"},
                                "creator": {"type": "string", "example": "Creator Username"},
                                "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"},
                                "is_saved": {"type": "boolean", "example": True}
                            }
                        }
                    }
                }
            }
        }
    )
    # def list(self, request, *args, **kwargs):
    #     queryset = self.get_queryset()
    #     total_cards_count = queryset.count()
    #
    #     page = self.paginate_queryset(queryset)
    #
    #     saved_cards_count = 0
    #     if request.user.is_authenticated:
    #         saved_cards_count = SavedCard.objects.filter(user=request.user).count()
    #
    #     if page is not None:
    #         serializer = self.get_serializer(page, many=True, context={'request': request})
    #         return self.get_paginated_response(serializer.data, saved_cards_count)
    #
    #     serializer = self.get_serializer(queryset, many=True, context={'request': request})
    #     return Response({
    #         "statusCode": 200,
    #         "messages": ["Cards retrieved successfully."],
    #         "total": total_cards_count,
    #         "page": 1,
    #         "perPage": total_cards_count if total_cards_count > 0 else 1,
    #         "result": serializer.data  # ✅ Each card will now have "is_saved"
    #     }, status=status.HTTP_200_OK)
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        total_cards_count = queryset.count()

        # Get page number and page size
        page_number = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('page_size', self.pagination_class.page_size))

        # Calculate the custom slice: from 0 to (page_number * per_page)
        end_index = page_number * per_page
        paged_queryset = queryset[:end_index]

        # Count saved cards for authenticated users
        saved_cards_count = 0
        if request.user.is_authenticated:
            saved_cards_count = SavedCard.objects.filter(user=request.user).count()

        serializer = self.get_serializer(paged_queryset, many=True, context={'request': request})

        return Response({
            "statusCode": 200,
            "messages": ["Cards retrieved successfully."],
            "total": total_cards_count,
            "page": page_number,
            "perPage": per_page,
            "result": serializer.data
        }, status=status.HTTP_200_OK)

    def get_paginated_response(self, data, saved_cards_count):
        return Response({
            "statusCode": 200,
            "messages": ["Cards retrieved successfully."],
            "total": self.paginator.page.paginator.count,
            "page": self.paginator.page.number,
            "perPage": self.paginator.page.paginator.per_page,
            "result": data,  # ✅ All cards in "result" will have "is_saved"
        })

    @extend_schema(
        request=CardSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Card created successfully."]
                    },
                    "result": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "example": 1},
                            "content": {"type": "string", "example": "This is a sample card"},
                            "creator": {"type": "string", "example": "Creator Username"},
                            "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"},
                            "gemini_response": {
                                "type": "string",
                                "example": "برای مهندس شدن باید ریاضیات و فیزیک را خوب یاد بگیری."
                            }
                        }
                    }
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Failed to create card."]
                    },
                    "errors": {"type": "object"}
                }
            }
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            self.perform_create(serializer)
            card_instance = serializer.instance
            card_data = serializer.data

            # Generate Gemini response
            try:
                gemini_handler = GeminiChatWishAPIView()
                user_message = card_data.get("content")
                challenge = request.data.get("challenge") or "چالش ۱"
                result = asyncio.run(gemini_handler.handle_rag_chat(user_message, card_data['id'], challenge))
                gemini_response = result.get("response", "")
                # bot_user = User.objects.get(username="بات تحلیل گر آرزو")

                bot_user = User.objects.get(username="بات تحلیلگر آرزو")

                Comment.objects.create(
                    card=card_instance,
                    creator=bot_user,
                    content=gemini_response
                )

            except Exception as e:
                gemini_response = f"خطا در دریافت پاسخ Gemini: {str(e)}"

            return Response({
                "statusCode": 200,
                "messages": ["Card created successfully."],
                "result": {
                    **card_data,
                    "gemini_response": gemini_response
                }
            }, status=status.HTTP_200_OK)

        return Response({
            "statusCode": 400,
            "messages": ["Failed to create card."],
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {"type": "array", "items": {"type": "string"},
                                 "example": ["Card retrieved successfully."]},
                    "result": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "example": 1},
                            "content": {"type": "string", "example": "This is a sample card"},
                            "creator": {"type": "string", "example": "Creator Username"},
                            "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"},
                            "is_saved": {"type": "boolean", "example": True}
                        }
                    }
                }
            },
            404: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 404},
                    "messages": {"type": "array", "items": {"type": "string"}, "example": ["Card not found."]}
                }
            }
        }
    )
    def retrieve(self, request, pk=None, *args, **kwargs):
        instance = get_object_or_404(Card, pk=pk)
        serializer = self.get_serializer(instance, context={'request': request})

        return Response({
            "statusCode": 200,
            "messages": ["Card retrieved successfully."],
            "result": serializer.data
        }, status=status.HTTP_200_OK)

    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Card updated successfully."]
                    },
                    "result": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "example": 1},
                            "content": {"type": "string", "example": "This is an updated card"},
                            "creator": {"type": "string", "example": "Creator Username"},
                            "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
                        }
                    }
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Failed to update card."]
                    },
                    "errors": {"type": "object"}
                }
            }
        }
    )
    def update(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=False)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "statusCode": 200,
                "messages": ["Card updated successfully."],
                "result": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            "statusCode": 400,
            "messages": ["Failed to update card."],
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Card partially updated successfully."]
                    },
                    "result": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "example": 1},
                            "content": {"type": "string", "example": "This is an updated card"},
                            "creator": {"type": "string", "example": "Creator Username"},
                            "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
                        }
                    }
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Failed to partially update card."]
                    },
                    "errors": {"type": "object"}
                }
            }
        }
    )
    def partial_update(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "statusCode": 200,
                "messages": ["Card partially updated successfully."],
                "result": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            "statusCode": 400,
            "messages": ["Failed to partially update card."],
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={
            204: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 204},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Card deleted successfully."]
                    }
                }
            },
            404: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 404},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Card not found."]
                    }
                }
            }
        }
    )
    def destroy(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            "statusCode": 204,
            "messages": ["Card deleted successfully."]
        }, status=status.HTTP_204_NO_CONTENT)


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all().order_by('-created_at')
    serializer_class = CommentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination  # Enable pagination

    def perform_create(self, serializer):
        card = self.request.data.get("card")  # Get card_id from request data
        if not card:
            raise serializers.ValidationError({"card_id": "This field is required."})

        card = get_object_or_404(Card, id=card)  # Fetch card instance
        serializer.save(creator=self.request.user, card=card)  # Save with creator & card

    @extend_schema(
        request=CommentSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Comment created successfully."]
                    },
                    "result": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "example": 1},
                            "content": {"type": "string", "example": "چی فکر می‌کنید بات تحلیل‌گر آرزو؟"},
                            "creator": {"type": "string", "example": "normal_user"},
                            "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
                        }
                    }
                },
                "description": (
                        "Creates a comment. "
                        "If the comment mentions the bot user `بات تحلیل‌گر آرزو`, "
                        "an AI-generated reply will be posted automatically as a new comment from the bot."
                )
            },
            400: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Failed to create comment."]
                    },
                    "errors": {"type": "object"}
                }
            }
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Save the comment
            comment = serializer.save()

            content = serializer.validated_data.get("content", "")
            card = comment.card
            mentions = serializer.data.get("mentions", [])

            # Check if the bot is mentioned
            if "بات تحلیل گر آرزو" in mentions or "بات تحلیلگر آرزو" in mentions:
                bot_user = ensure_bot_user()
                try:
                    user_message = comment.content
                    challenge = request.data.get("challenge") or "چالش ۱"

                    gemini_handler = GeminiChatWishAPIView()
                    gemini_response = asyncio.run(
                        gemini_handler.handle_rag_chat(user_message, card.id, challenge)
                    ).get("response", "")

                    # Create the bot's comment in response
                    Comment.objects.create(
                        card=card,
                        creator=bot_user,
                        content=gemini_response,
                        parent=comment
                    )
                except Exception as e:
                    print(f"Gemini Error: {e}")  # Log AI failure

            return Response({
                "statusCode": 200,
                "messages": ["Comment created successfully."],
                "result": self.get_serializer(comment).data
            }, status=status.HTTP_200_OK)

        return Response({
            "statusCode": 400,
            "messages": ["Failed to create comment."],
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {"type": "array", "items": {"type": "string"},
                                 "example": ["Comments retrieved successfully."]},
                    "total": {"type": "integer", "example": 0},
                    "page": {"type": "integer", "example": 1},
                    "perPage": {"type": "integer", "example": 10},
                    "result": {"type": "array", "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "example": 1},
                            "content": {"type": "string", "example": "This is a sample comment"},
                            "creator": {"type": "string", "example": "Creator Username"},
                            "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
                        }
                    }}
                }
            }
        }
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "statusCode": 200,
            "messages": ["Comments retrieved successfully."],
            "total": queryset.count(),
            "page": 1,
            "perPage": queryset.count() if queryset.count() > 0 else 1,  # Corrected perPage
            "result": serializer.data
        }, status=status.HTTP_200_OK)

    def get_paginated_response(self, data):
        """
        Customize the paginated response format.
        """
        return Response({
            "statusCode": 200,
            "messages": ["Comments retrieved successfully."],
            "total": self.paginator.page.paginator.count,
            "page": self.paginator.page.number,
            "perPage": self.paginator.page.paginator.per_page,
            "result": data,
        })

    # @extend_schema(
    #     request={
    #         "application/json": {
    #             "type": "object",
    #             "properties": {
    #                 "comment_id": {"type": "integer", "example": 1},
    #                 "content": {"type": "string", "example": "Updated comment content"}
    #             },
    #             "required": ["comment_id", "content"]
    #         }
    #     },
    #     responses={
    #         200: {
    #             "type": "object",
    #             "properties": {
    #                 "statusCode": {"type": "integer", "example": 200},
    #                 "messages": {"type": "array", "items": {"type": "string"},
    #                              "example": ["Comment updated successfully."]},
    #                 "result": {
    #                     "type": "object",
    #                     "properties": {
    #                         "id": {"type": "integer", "example": 1},
    #                         "content": {"type": "string", "example": "Updated comment content"},
    #                         "creator": {"type": "string", "example": "Creator Username"},
    #                         "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
    #                     }
    #                 }
    #             }
    #         },
    #         400: {
    #             "type": "object",
    #             "properties": {
    #                 "statusCode": {"type": "integer", "example": 400},
    #                 "messages": {"type": "array", "items": {"type": "string"},
    #                              "example": ["Failed to update comment."]},
    #                 "errors": {"type": "object"}
    #             }
    #         },
    #         404: {
    #             "type": "object",
    #             "properties": {
    #                 "statusCode": {"type": "integer", "example": 404},
    #                 "messages": {"type": "array", "items": {"type": "string"},
    #                              "example": ["Comment not found."]},
    #             }
    #         }
    #     }
    # )
    # def update(self, request, *args, **kwargs):
    #     """Update a comment by providing `comment_id` in the request body instead of the query."""
    #     comment_id = request.data.get("comment_id")  # ✅ Read from the request body
    #
    #     if not comment_id:
    #         return Response({
    #             "statusCode": 400,
    #             "messages": ["Comment ID is required."],
    #             "errors": {"comment_id": ["This field is required."]}
    #         }, status=status.HTTP_400_BAD_REQUEST)
    #
    #     # Get the comment object
    #     comment = get_object_or_404(Comment, id=comment_id)
    #
    #     # Validate & update the comment
    #     serializer = self.get_serializer(comment, data=request.data, partial=True)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response({
    #             "statusCode": 200,
    #             "messages": ["Comment updated successfully."],
    #             "result": serializer.data
    #         }, status=status.HTTP_200_OK)
    #     else:
    #         return Response({
    #             "statusCode": 400,
    #             "messages": ["Failed to update comment."],
    #             "errors": serializer.errors
    #         }, status=status.HTTP_400_BAD_REQUEST)
    #
    # @extend_schema(
    #     responses={
    #         204: {  # No Content
    #             "type": "object",
    #             "properties": {
    #                 "statusCode": {"type": "integer", "example": 204},
    #                 "messages": {"type": "array", "items": {"type": "string"},
    #                              "example": ["Comment deleted successfully."]},
    #             }
    #         },
    #         404: {
    #             "type": "object",
    #             "properties": {
    #                 "statusCode": {"type": "integer", "example": 404},
    #                 "messages": {"type": "array", "items": {"type": "string"},
    #                              "example": ["Comment not found."]},
    #             }
    #         }
    #     }
    # )
    # def destroy(self, request, *args, **kwargs):
    #     try:
    #         instance = self.get_object()
    #         self.perform_destroy(instance)
    #         return Response({
    #             "statusCode": 204,
    #             "messages": ["Comment deleted successfully."]
    #         }, status=status.HTTP_204_NO_CONTENT)
    #     except Exception as e:  # Handle exceptions, such as object not found
    #         return Response({
    #             "statusCode": 404,
    #             "messages": ["Comment not found."]
    #         }, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {"type": "array", "items": {"type": "string"},
                                 "example": ["Comment retrieved successfully."]},
                    "result": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "example": 1},
                            "content": {"type": "string", "example": "This is a sample comment"},
                            "creator": {"type": "string", "example": "Creator Username"},
                            "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
                        }
                    }
                }
            },
            404: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 404},
                    "messages": {"type": "array", "items": {"type": "string"},
                                 "example": ["Comment not found."]},
                }
            }
        }
    )
    def retrieve(self, request, pk=None, *args, **kwargs):
        """
        Retrieve a specific comment by its ID.
        """
        try:
            instance = get_object_or_404(Comment, pk=pk)
            serializer = self.get_serializer(instance)
            return Response({
                "statusCode": 200,
                "messages": ["Comment retrieved successfully."],
                "result": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "statusCode": 404,
                "messages": ["Comment not found."]
            }, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        responses={
            204: {  # No Content
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 204},
                    "messages": {"type": "array", "items": {"type": "string"},
                                 "example": ["Comment deleted successfully."]},
                }
            },
            403: {  # Forbidden - Not the owner
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 403},
                    "messages": {"type": "array", "items": {"type": "string"},
                                 "example": ["You do not have permission to delete this comment."]},
                }
            },
            404: {  # Not Found
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 404},
                    "messages": {"type": "array", "items": {"type": "string"},
                                 "example": ["Comment not found."]},
                }
            },
            400: {  # Bad Request - Unexpected Error
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {"type": "array", "items": {"type": "string"},
                                 "example": ["An error occurred while deleting the comment."]},
                    "error": {"type": "string", "example": "Detailed error message here"}
                }
            }
        }
    )
    def destroy(self, request, *args, **kwargs):
        """
        Delete a comment. Only the comment creator or an admin can delete it.
        """
        try:
            instance = self.get_object()

            # Check if the request user is the creator or an admin
            if request.user != instance.creator and not request.user.is_staff:
                return Response({
                    "statusCode": 403,
                    "messages": ["You do not have permission to delete this comment."],
                    "result": ""
                }, status=status.HTTP_403_FORBIDDEN)

            self.perform_destroy(instance)
            return Response({
                "statusCode": 204,
                "messages": ["Comment deleted successfully."],
                "result": ""
            }, status=status.HTTP_204_NO_CONTENT)

        except Comment.DoesNotExist:
            return Response({
                "statusCode": 404,
                "messages": ["Comment not found."],
                "result": ""
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({
                "statusCode": 400,
                "messages": ["An error occurred while deleting the comment."],
                "error": str(e),
                "result": ""
            }, status=status.HTTP_400_BAD_REQUEST)


class CardCommentsRepliesAPIView(APIView):
    permission_classes = []

    def get(self, request, card_id, format=None):
        card = get_object_or_404(Card, id=card_id)

        all_comments = Comment.objects.filter(card=card).order_by('created_at')

        comment_serializer = FlatCommentWithMetaSerializer(
            all_comments,
            many=True,
            context={'request': request, 'card': card}
        )
        card_serializer = CardDetailSerializer(card, context={'request': request})

        return Response({
            "statusCode": 200,
            "messages": ["Comments and replies retrieved successfully."],
            "total": all_comments.count(),
            "result": {
                "card": card_serializer.data,
                "comments": comment_serializer.data
            }
        }, status=status.HTTP_200_OK)


# class CardCommentsRepliesAPIView(APIView):
#     permission_classes = []
#
#     @extend_schema(
#         responses={
#             200: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 200},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Comments and replies retrieved successfully."]
#                     },
#                     "total": {"type": "integer", "example": 5},
#                     "result": {
#                         "type": "object",
#                         "properties": {
#                             "card_id": {"type": "integer", "example": 1},
#                             "comments": {
#                                 "type": "array",
#                                 "items": {
#                                     "type": "object",
#                                     "properties": {
#                                         "id": {"type": "integer", "example": 1},
#                                         "content": {"type": "string", "example": "This is a comment"},
#                                         "card": {"type": "integer", "example": 1},
#                                         "creator": {"type": "string", "example": "User1"},
#                                         "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"},
#                                         "updated_at": {"type": "string", "example": "2023-03-05T12:34:56Z"},
#                                         "replies": {
#                                             "type": "array",
#                                             "items": {
#                                                 "type": "object",
#                                                 "properties": {
#                                                     "id": {"type": "integer", "example": 1},
#                                                     "comment": {"type": "integer", "example": 1},
#                                                     "user": {"type": "string", "example": "User2"},
#                                                     "content": {"type": "string", "example": "This is a reply"},
#                                                     "created_at": {"type": "string", "example": "2023-03-05T13:00:00Z"}
#                                                 }
#                                             }
#                                         }
#                                     }
#                                 }
#                             }
#                         }
#                     }
#                 }
#             },
#             404: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 404},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Card not found."]
#                     }
#                 }
#             }
#         }
#     )
#     def get(self, request, card_id, format=None):
#         card = get_object_or_404(Card, id=card_id)
#
#         # Only fetch top-level comments
#         comments = Comment.objects.filter(card=card, parent__isnull=True).order_by('-created_at')
#
#         serializer = CommentWithRepliesCreatorSerializer(comments, many=True, context={'request': request})
#
#         return Response({
#             "statusCode": 200,
#             "messages": ["Comments and replies retrieved successfully."],
#             "total": comments.count(),
#             "result": {
#                 "card_id": card.id,
#                 "comments": serializer.data
#             }
#         }, status=status.HTTP_200_OK)


class UpdateCommentView(APIView):
    """API endpoint for updating a comment using comment_id in the request body."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "comment_id": {"type": "integer", "example": 1},
                    "content": {"type": "string", "example": "Updated comment with @بات تحلیل گر آرزو"},
                    "mentions": {
                        "type": "array",
                        "items": {"type": "integer", "example": 2},
                        "description": "Optional list of user IDs to mention"
                    }
                },
                "required": ["comment_id", "content"]
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {"type": "array", "items": {"type": "string"}},
                    "result": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "content": {"type": "string"},
                            "creator": {"type": "string"},
                            "mentions": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "created_at": {"type": "string"}
                        }
                    }
                }
            }
        }
    )
    def put(self, request, *args, **kwargs):
        comment_id = request.data.get("comment_id")
        if not comment_id:
            return Response({
                "statusCode": 400,
                "messages": ["Comment ID is required."],
                "errors": {"comment_id": ["This field is required."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        comment = get_object_or_404(Comment, id=comment_id)

        if request.user != comment.creator and not request.user.is_staff:
            return Response({
                "statusCode": 403,
                "messages": ["You do not have permission to update this comment."]
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = CommentSerializer(comment, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            comment = serializer.save()

            # Mention handling
            content = serializer.validated_data.get("content", "")
            content_mentions = extract_mentions(content)
            passed_mentions = request.data.get("mentions", [])
            all_mentions = list(set(passed_mentions) | set(content_mentions))
            comment.mentions.set(all_mentions)

            # Formatted for response
            formatted_mentions = [
                user.username if user.username else f"u{user.id}"
                for user in comment.mentions.all()
            ]

            # Gemini AI bot handling
            try:
                User = get_user_model()
                # bot_user = User.objects.get(username="بات تحلیل گر آرزو")  #local version
                bot_user = User.objects.get(username="بات تحلیلگر آرزو")
            except User.DoesNotExist:
                bot_user = None

            if bot_user and bot_user in comment.mentions.all():
                try:
                    user_message = comment.content
                    challenge = request.data.get("challenge", "چالش ۱")

                    gemini_handler = GeminiChatWishAPIView()
                    gemini_response = asyncio.run(
                        gemini_handler.handle_rag_chat(user_message, comment.card.id, challenge)
                    ).get("response", "")

                    Comment.objects.create(
                        card=comment.card,
                        creator=bot_user,
                        content=gemini_response,
                        parent=comment
                    )
                except Exception as e:
                    print(f"Gemini Error: {e}")

            return Response({
                "statusCode": 200,
                "messages": ["Comment updated successfully."],
                "result": {
                    "id": comment.id,
                    "content": comment.content,
                    "creator": comment.creator.username if comment.creator.username else f"u{comment.creator.id}",
                    "mentions": formatted_mentions,
                    "created_at": comment.created_at.isoformat()
                }
            }, status=status.HTTP_200_OK)

        return Response({
            "statusCode": 400,
            "messages": ["Failed to update comment."],
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


# class CommentReplyViewSet(viewsets.ModelViewSet):
#     queryset = CommentReply.objects.all().order_by('-created_at')  # Order by latest replies
#     serializer_class = CommentReplySerializer
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [permissions.IsAuthenticated]  # Only authenticated users can reply
#
#     def perform_create(self, serializer):
#         """Assign the logged-in user as the creator of the reply"""
#         serializer.save(user=self.request.user)
#
#     @extend_schema(
#         responses={
#             200: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 200},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Replies retrieved successfully."]
#                     },
#                     "total": {"type": "integer", "example": 10},
#                     "result": {
#                         "type": "array",
#                         "items": {
#                             "type": "object",
#                             "properties": {
#                                 "id": {"type": "integer", "example": 1},
#                                 "content": {"type": "string", "example": "This is a reply"},
#                                 "user": {"type": "string", "example": "Username"},
#                                 "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
#                             }
#                         }
#                     }
#                 }
#             },
#             404: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 404},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Comment not found."]
#                     }
#                 }
#             }
#         }
#     )
#     @action(detail=False, methods=['get'], url_path='by-comment/(?P<comment_id>[^/.]+)')
#     def get_replies_by_comment(self, request, comment_id):
#         """
#         Get all replies for a specific comment ID
#         """
#         comment = get_object_or_404(Comment, id=comment_id)
#         replies = CommentReply.objects.filter(comment=comment).order_by('-created_at')
#         serializer = self.get_serializer(replies, many=True)
#
#         return Response({
#             "statusCode": 200,
#             "messages": ["Replies retrieved successfully."],
#             "total": replies.count(),
#             "result": serializer.data
#         }, status=status.HTTP_200_OK)
#
#     @extend_schema(
#         responses={
#             200: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 200},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Comment replies retrieved successfully."]
#                     },
#                     "total": {"type": "integer", "example": 50},
#                     "page": {"type": "integer", "example": 1},
#                     "perPage": {"type": "integer", "example": 10},
#                     "result": {
#                         "type": "array",
#                         "items": {
#                             "type": "object",
#                             "properties": {
#                                 "id": {"type": "integer", "example": 1},
#                                 "content": {"type": "string", "example": "This is a reply"},
#                                 "user": {"type": "string", "example": "Username"},
#                                 "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
#                             }
#                         }
#                     }
#                 }
#             }
#         }
#     )
#     def list(self, request, *args, **kwargs):
#         queryset = self.get_queryset()
#         page = self.paginate_queryset(queryset)  # Paginate the queryset
#
#         if page is not None:
#             serializer = self.get_serializer(page, many=True)
#             return self.get_paginated_response(serializer.data)
#
#         serializer = self.get_serializer(queryset, many=True)
#         return Response({
#             "statusCode": 200,
#             "messages": ["Comment replies retrieved successfully."],
#             "total": queryset.count(),
#             "page": 1,
#             "perPage": queryset.count() if queryset.count() > 0 else 1,
#             "result": serializer.data
#         }, status=status.HTTP_200_OK)
#
#     def get_paginated_response(self, data):
#         """
#         Customize the paginated response format.
#         """
#         return Response({
#             "statusCode": 200,
#             "messages": ["Comment replies retrieved successfully."],
#             "total": self.paginator.page.paginator.count,
#             "page": self.paginator.page.number,
#             "perPage": self.paginator.page.paginator.per_page,
#             "result": data,
#         })
#
#     @extend_schema(
#         responses={
#             200: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 200},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Comment reply created successfully."]
#                     },
#                     "result": {
#                         "type": "object",
#                         "properties": {
#                             "id": {"type": "integer", "example": 1},
#                             "content": {"type": "string", "example": "This is a newly created reply"},
#                             "user": {"type": "string", "example": "Username"},
#                             "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
#                         }
#                     }
#                 }
#             },
#             400: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 400},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Failed to create comment reply."]
#                     },
#                     "errors": {"type": "object"}
#                 }
#             }
#         }
#     )
#     def create(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#
#         if serializer.is_valid():
#             comment = request.data.get("comment")  # Extract comment_id
#
#             if not comment:
#                 return Response({
#                     "statusCode": 400,
#                     "messages": ["comment_id is required."],
#                     "errors": {"comment_id": ["This field is required."]}
#                 }, status=status.HTTP_400_BAD_REQUEST)
#
#             comment = get_object_or_404(Comment, id=comment)  # Ensure comment exists
#
#             # Save with user instead of creator
#             serializer.save(comment=comment, user=request.user)
#
#             return Response({
#                 "statusCode": 200,
#                 "messages": ["Comment reply created successfully."],
#                 "result": serializer.data
#             }, status=status.HTTP_200_OK)
#
#         return Response({
#             "statusCode": 400,
#             "messages": ["Failed to create comment reply."],
#             "errors": serializer.errors
#         }, status=status.HTTP_400_BAD_REQUEST)
#
#     @extend_schema(
#         responses={
#             200: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 200},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Comment reply retrieved successfully."]
#                     },
#                     "result": {
#                         "type": "object",
#                         "properties": {
#                             "id": {"type": "integer", "example": 1},
#                             "content": {"type": "string", "example": "This is a reply"},
#                             "user": {"type": "string", "example": "Username"},
#                             "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
#                         }
#                     }
#                 }
#             },
#             404: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 404},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Comment reply not found."]
#                     }
#                 }
#             }
#         }
#     )
#     def retrieve(self, request, pk=None, *args, **kwargs):
#         instance = get_object_or_404(CommentReply, pk=pk)
#         serializer = self.get_serializer(instance)
#         return Response({
#             "statusCode": 200,
#             "messages": ["Comment reply retrieved successfully."],
#             "result": serializer.data
#         }, status=status.HTTP_200_OK)
#
#     # @extend_schema(
#     #     responses={
#     #         200: {
#     #             "type": "object",
#     #             "properties": {
#     #                 "statusCode": {"type": "integer", "example": 200},
#     #                 "messages": {
#     #                     "type": "array",
#     #                     "items": {"type": "string"},
#     #                     "example": ["Comment reply updated successfully."]
#     #                 },
#     #                 "result": {
#     #                     "type": "object",
#     #                     "properties": {
#     #                         "id": {"type": "integer", "example": 1},
#     #                         "content": {"type": "string", "example": "This is an updated reply"},
#     #                         "user": {"type": "string", "example": "Username"},
#     #                         "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
#     #                     }
#     #                 }
#     #             }
#     #         },
#     #         400: {
#     #             "type": "object",
#     #             "properties": {
#     #                 "statusCode": {"type": "integer", "example": 400},
#     #                 "messages": {
#     #                     "type": "array",
#     #                     "items": {"type": "string"},
#     #                     "example": ["Failed to update comment reply."]
#     #                 },
#     #                 "errors": {"type": "object"}
#     #             }
#     #         }
#     #     }
#     # )
#     # def update(self, request, pk=None, *args, **kwargs):
#     #     instance = self.get_object()
#     #     serializer = self.get_serializer(instance, data=request.data, partial=False)
#     #     if serializer.is_valid():
#     #         serializer.save()
#     #         return Response({
#     #             "statusCode": 200,
#     #             "messages": ["Comment reply updated successfully."],
#     #             "result": serializer.data
#     #         }, status=status.HTTP_200_OK)
#     #     return Response({
#     #         "statusCode": 400,
#     #         "messages": ["Failed to update comment reply."],
#     #         "errors": serializer.errors
#     #     }, status=status.HTTP_400_BAD_REQUEST)
#
#     @extend_schema(
#         responses={
#             200: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 200},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Comment reply partially updated successfully."]
#                     },
#                     "result": {
#                         "type": "object",
#                         "properties": {
#                             "id": {"type": "integer", "example": 1},
#                             "content": {"type": "string", "example": "This is an updated reply"},
#                             "user": {"type": "string", "example": "Username"},
#                             "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
#                         }
#                     }
#                 }
#             },
#             400: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 400},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Failed to partially update comment reply."]
#                     },
#                     "errors": {"type": "object"}
#                 }
#             }
#         }
#     )
#     def partial_update(self, request, pk=None, *args, **kwargs):
#         instance = self.get_object()
#         serializer = self.get_serializer(instance, data=request.data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return Response({
#                 "statusCode": 200,
#                 "messages": ["Comment reply partially updated successfully."],
#                 "result": serializer.data
#             }, status=status.HTTP_200_OK)
#         return Response({
#             "statusCode": 400,
#             "messages": ["Failed to partially update comment reply."],
#             "errors": serializer.errors
#         }, status=status.HTTP_400_BAD_REQUEST)
#
#     @extend_schema(
#         responses={
#             204: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 204},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Comment reply deleted successfully."]
#                     }
#                 }
#             },
#             404: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 404},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Comment reply not found."]
#                     }
#                 }
#             }
#         }
#     )
#     def destroy(self, request, pk=None, *args, **kwargs):
#         instance = self.get_object()
#         self.perform_destroy(instance)
#         return Response({
#             "statusCode": 204,
#             "messages": ["Comment reply deleted successfully."],
#             "result": ""
#         }, status=status.HTTP_204_NO_CONTENT)


# class CommentReplyUpdateViewSet(GenericAPIView):
#     queryset = CommentReply.objects.all().order_by('-created_at')
#     serializer_class = CommentReplySerializer
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [permissions.IsAuthenticated]
#
#     @extend_schema(
#         request={
#             "type": "object",
#             "properties": {
#                 "id": {"type": "integer", "example": 1},
#                 "content": {"type": "string", "example": "This is an updated reply"}
#             },
#             "required": ["id", "content"]
#         },
#         responses={
#             200: {
#                 "type": "object",
#                 "properties": dict(statusCode={"type": "integer", "example": 200}, messages={
#                     "type": "array",
#                     "items": {"type": "string"},
#                     "example": ["Comment reply updated successfully."]
#                 }, result={
#                     "type": "object",
#                     "properties": {
#                         "id": {"type": "integer", "example": 1},
#                         "content": {"type": "string", "example": "This is an updated reply"},
#                         "user": {"type": "string", "example": "Username"},
#                         "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"}
#                     }
#                 })
#             },
#             400: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 400},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Failed to update comment reply."]
#                     },
#                     "errors": {"type": "object"}
#                 }
#             },
#             403: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 403},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["You do not have permission to edit this comment reply."]
#                     }
#                 }
#             },
#             404: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 404},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Comment reply not found."]
#                     }
#                 }
#             }
#         }
#     )
#     def update(self, request, *args, **kwargs):
#         """
#         Update a comment reply. The ID is taken from the request body, not the URL.
#         """
#         comment_id = request.data.get("id")
#         if not comment_id:
#             return Response({
#                 "statusCode": 400,
#                 "messages": ["ID is required in the request body."]
#             }, status=status.HTTP_400_BAD_REQUEST)
#
#         instance = get_object_or_404(CommentReply, pk=comment_id)
#
#         # Check if the user is the owner of the comment or an admin
#         if request.user != instance.user and not request.user.is_staff:
#             return Response({
#                 "statusCode": 403,
#                 "messages": ["You do not have permission to edit this comment reply."]
#             }, status=status.HTTP_403_FORBIDDEN)
#
#         serializer = self.get_serializer(instance, data=request.data, partial=False)
#         if serializer.is_valid():
#             serializer.save()
#             return Response({
#                 "statusCode": 200,
#                 "messages": ["Comment reply updated successfully."],
#                 "result": serializer.data
#             }, status=status.HTTP_200_OK)
#
#         return Response({
#             "statusCode": 400,
#             "messages": ["Failed to update comment reply."],
#             "errors": serializer.errors
#         }, status=status.HTTP_400_BAD_REQUEST)


# class CardCommentsRepliesAPIView(APIView):
#     permission_classes = []
#
#     @extend_schema(
#         responses={
#             200: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 200},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Comments and replies retrieved successfully."]
#                     },
#                     "total": {"type": "integer", "example": 5},
#                     "result": {
#                         "type": "object",
#                         "properties": {
#                             "card_id": {"type": "integer", "example": 1},
#                             "comments": {
#                                 "type": "array",
#                                 "items": {
#                                     "type": "object",
#                                     "properties": {
#                                         "id": {"type": "integer", "example": 1},
#                                         "content": {"type": "string", "example": "This is a comment"},
#                                         "card": {"type": "integer", "example": 1},
#                                         "creator": {"type": "string", "example": "User1"},
#                                         "created_at": {"type": "string", "example": "2023-03-05T12:34:56Z"},
#                                         "updated_at": {"type": "string", "example": "2023-03-05T12:34:56Z"},
#                                         "replies": {
#                                             "type": "array",
#                                             "items": {
#                                                 "type": "object",
#                                                 "properties": {
#                                                     "id": {"type": "integer", "example": 1},
#                                                     "comment": {"type": "integer", "example": 1},
#                                                     "user": {"type": "string", "example": "User2"},
#                                                     "content": {"type": "string", "example": "This is a reply"},
#                                                     "created_at": {"type": "string", "example": "2023-03-05T13:00:00Z"}
#                                                 }
#                                             }
#                                         }
#                                     }
#                                 }
#                             }
#                         }
#                     }
#                 }
#             },
#             404: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 404},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Card not found."]
#                     }
#                 }
#             }
#         }
#     )
#     def get(self, request, card_id, format=None):
#         # Retrieve the card or return a 404 response if not found
#         card = get_object_or_404(Card, id=card_id)
#         # Retrieve all comments for this card
#         comments = Comment.objects.filter(card=card).order_by('-created_at')
#         serializer = CommentWithRepliesCreatorSerializer(comments, many=True, context={'request': request})
#
#         return Response({
#             "statusCode": 200,
#             "messages": ["Comments and replies retrieved successfully."],
#             "total": comments.count(),
#             "result": {
#                 "card_id": card.id,
#                 "comments": serializer.data
#             }
#         }, status=status.HTTP_200_OK)

class CustomTokenRefreshView(TokenRefreshView):
    @extend_schema(
        description="# Extract the token from query parameters (e.g., ?refresh=<token>)",
        parameters=[
            OpenApiParameter(
                name="refresh",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Refresh token to get a new access token.",
                required=True
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Token refreshed successfully."]
                    },
                    "result": {
                        "type": "object",
                        "properties": {
                            "accessToken": {"type": "string", "example": "new_access_token"},
                            "refreshToken": {"type": "string", "example": "provided_refresh_token"}
                        }
                    }
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Refresh token not provided."]
                    }
                }
            }
        }
    )
    def get(self, request, *args, **kwargs):
        # Extract the token from query parameters (e.g., ?refresh=<token>)
        refresh_token = request.query_params.get('refresh')
        if not refresh_token:
            return Response({
                "statusCode": 400,
                "messages": ["Refresh token not provided."]
            }, status=status.HTTP_400_BAD_REQUEST)

        # Prepare the data for the serializer
        data = {"refresh": refresh_token}
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        return Response({
            "statusCode": 200,
            "messages": ["Token refreshed successfully."],
            "result": {
                "accessToken": serializer.validated_data.get("access"),
                "refreshToken": refresh_token  # Include the provided refresh token
            }
        }, status=status.HTTP_200_OK)


class SavedCardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Retrieve all saved cards",
        description="Retrieve all saved cards for the authenticated user.",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Saved cards retrieved successfully."]
                    },
                    "total": {"type": "integer", "example": 5},
                    "result": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer", "example": 1},
                                "user": {"type": "string", "example": "username"},
                                "card": {"type": "string", "example": "Card Title"},
                                "card_id": {"type": "integer", "example": 1},
                                "saved_at": {"type": "string", "example": "2024-03-10T14:30:00Z"}
                            }
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        """Retrieve all saved cards for the authenticated user."""
        try:
            saved_cards = SavedCard.objects.filter(user=request.user)
            serializer = SavedCardSerializer(saved_cards, many=True)
            return Response({
                "statusCode": 200,
                "messages": ["Saved cards retrieved successfully."],
                "total": saved_cards.count(),
                "result": serializer.data
            }, status=status.HTTP_200_OK)
        except DatabaseError:
            return Response({
                "statusCode": 500,
                "messages": ["Database error occurred while retrieving saved cards."]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        summary="Save a new card",
        description="Save a new card for the authenticated user by providing `card_id`.",
        request=SavedCardSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Card saved successfully."]
                    },
                    "result": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "example": 1},
                            "user": {"type": "string", "example": "username"},
                            "card": {"type": "string", "example": "Card Title"},
                            "card_id": {"type": "integer", "example": 1},
                            "saved_at": {"type": "string", "example": "2024-03-10T14:30:00Z"}
                        }
                    }
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Card ID is required."]
                    }
                }
            },
            500: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 500},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Database error occurred while saving the card."]
                    }
                }
            }
        }
    )
    def post(self, request):
        """Save a new card for the authenticated user."""
        try:
            card_id = request.data.get("card_id")  # Get card_id from request body
            if not card_id:
                return Response({
                    "statusCode": 400,
                    "messages": ["Card ID is required."]
                }, status=status.HTTP_400_BAD_REQUEST)

            serializer = SavedCardSerializer(data=request.data, context={'request': request})
            if serializer.is_valid(raise_exception=True):
                try:
                    saved_instance = serializer.save(user=request.user)
                    return Response({
                        "statusCode": 200,
                        "messages": ["Card saved successfully."],
                        "result": SavedCardSerializer(saved_instance).data
                    }, status=status.HTTP_200_OK)
                except IntegrityError:
                    return Response({
                        "statusCode": 400,
                        "messages": ["You have already saved this card."]
                    }, status=status.HTTP_400_BAD_REQUEST)

        except ValidationError as e:
            return Response({
                "statusCode": 400,
                "messages": e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError:
            return Response({
                "statusCode": 500,
                "messages": ["Database error occurred while saving the card."]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    #
    # @extend_schema(
    #     summary="Delete a saved card",
    #     description="Delete a saved card based on `card_id` provided in the URL.",
    #     parameters=[
    #         OpenApiParameter(
    #             name="card_id",
    #             description="ID of the card to remove from saved list",
    #             required=True,
    #             type=int,
    #             location=OpenApiParameter.PATH,
    #         )
    #     ],
    #     responses={
    #         200: {
    #             "type": "object",
    #             "properties": {
    #                 "statusCode": {"type": "integer", "example": 200},
    #                 "messages": {
    #                     "type": "array",
    #                     "items": {"type": "string"},
    #                     "example": ["Card removed from saved list."]
    #                 }
    #             }
    #         },
    #         404: {
    #             "type": "object",
    #             "properties": {
    #                 "statusCode": {"type": "integer", "example": 404},
    #                 "messages": {
    #                     "type": "array",
    #                     "items": {"type": "string"},
    #                     "example": ["Saved card not found."]
    #                 }
    #             }
    #         }
    #     }
    # )
    # def delete(self, request):
    #     """Delete a saved card based on `card_id`."""
    #     card_id = request.data.get("card_id")
    #     if not card_id:
    #         return Response({
    #             "statusCode": 400,
    #             "messages": ["Card ID is required."]
    #         }, status=status.HTTP_400_BAD_REQUEST)
    #     try:
    #         saved_card = get_object_or_404(SavedCard, user=request.user, card_id=card_id)
    #         saved_card.delete()
    #         return Response({
    #             "statusCode": 200,
    #             "messages": ["Card removed from saved list."]
    #         }, status=status.HTTP_200_OK)
    #     except DatabaseError:
    #         return Response({
    #             "statusCode": 500,
    #             "messages": ["Database error occurred while deleting the card."]
    #         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SavedCardDeleteAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Delete a saved card",
        description="Delete a saved card based on `card_id` provided in the URL.",
        parameters=[
            OpenApiParameter(
                name="card_id",
                description="ID of the card to remove from saved list",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Card removed from saved list."]
                    }
                }
            },
            404: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 404},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Saved card not found."]
                    }
                }
            }
        }
    )
    def delete(self, request, card_id):
        """Delete a saved card based on `card_id`."""
        try:
            saved_card = get_object_or_404(SavedCard, user=request.user, card_id=card_id)
            saved_card.delete()
            return Response({
                "statusCode": 200,
                "messages": ["Card removed from saved list."]
            }, status=status.HTTP_200_OK)
        except DatabaseError:
            return Response({
                "statusCode": 500,
                "messages": ["Database error occurred while deleting the card."],
                "result": ""
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CommentLikeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Like a comment",
        description="Like a specific comment by providing the `comment_id` in the request body.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "comment_id": {"type": "integer", "example": 1}
                },
                "required": ["comment_id"]
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Like added successfully"]
                    },
                    "result": {"type": "object"}  # Placeholder for serialized comment data
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Already liked", "Comment ID is required"]
                    },
                    "result": {}
                }
            }
        }
    )
    def post(self, request):
        """Like a comment by providing comment_id in the request body"""
        user = request.user
        comment_id = request.data.get("comment_id")

        if not comment_id:
            return Response({
                "statusCode": 400,
                "messages": ["Comment ID is required"],
                "result": []
            }, status=status.HTTP_400_BAD_REQUEST)

        comment = get_object_or_404(Comment, id=comment_id)

        if CommentLike.objects.filter(user=user, comment=comment).exists():
            return Response({
                "statusCode": 400,
                "messages": ["Already liked"],
                "result": []
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create Like Entry
        CommentLike.objects.create(user=user, comment=comment)
        comment.like_count += 1
        comment.save()

        # Serialize and return updated comment
        serializer = CommentSerializer(comment, context={"request": request})
        return Response({
            "statusCode": 200,
            "messages": ["Like added successfully"],
            "result": serializer.data
        }, status=status.HTTP_200_OK)


class CommentUnlikeView(GenericAPIView):
    """View to handle unliking a comment."""

    @extend_schema(
        summary="Unlike a comment",
        description="Unlike a specific comment by providing the comment_id in the query parameters.",
        parameters=[
            OpenApiParameter(
                name="comment_id",
                description="ID of the comment to unlike",
                required=True,
                type=OpenApiTypes.INT
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Like removed successfully"]
                    },
                    "result": {"type": "object"}  # Placeholder for serialized comment data
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Not liked yet", "Comment ID is required"]
                    },
                    "result": {}
                }
            }
        }
    )
    def delete(self, request):
        """Unlike a comment by providing comment_id in the query parameters"""
        user = request.user
        comment_id = request.query_params.get("comment_id")  # ✅ Read from query parameters

        if not comment_id:
            return Response({
                "statusCode": 400,
                "messages": ["Comment ID is required"],
                "result": []
            }, status=status.HTTP_400_BAD_REQUEST)

        comment = get_object_or_404(Comment, id=comment_id)

        like = CommentLike.objects.filter(user=user, comment=comment).first()
        if not like:
            return Response({
                "statusCode": 400,
                "messages": ["Not liked yet"],
                "result": []
            }, status=status.HTTP_400_BAD_REQUEST)

        # Remove Like
        like.delete()
        comment.like_count -= 1
        comment.save()

        # Serialize and return updated comment
        serializer = CommentSerializer(comment, context={"request": request})
        return Response({
            "statusCode": 200,
            "messages": ["Like removed successfully"],
            "result": serializer.data
        }, status=status.HTTP_200_OK)


# class CommentReplyLikeView(APIView):
#     permission_classes = [IsAuthenticated]
#
#     @extend_schema(
#         summary="Like a reply",
#         description="Like a specific reply by providing the `reply_id` in the request body.",
#         request={
#             "application/json": {
#                 "type": "object",
#                 "properties": {
#                     "reply_id": {"type": "integer", "example": 1}
#                 },
#                 "required": ["reply_id"]
#             }
#         },
#         responses={
#             200: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 200},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Like added successfully"]
#                     },
#                     "result": {"type": "object"}  # Placeholder for serialized reply data
#                 }
#             },
#             400: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 400},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Already liked", "Reply ID is required"]
#                     },
#                     "result": {}
#                 }
#             }
#         }
#     )
#     def post(self, request):
#         """Like a reply by providing reply_id in the request body"""
#         user = request.user
#         reply_id = request.data.get("reply_id")
#
#         if not reply_id:
#             return Response({
#                 "statusCode": 400,
#                 "messages": ["Reply ID is required"],
#                 "result": []
#             }, status=status.HTTP_400_BAD_REQUEST)
#
#         reply = get_object_or_404(CommentReply, id=reply_id)
#
#         if CommentReplyLike.objects.filter(user=user, reply=reply).exists():
#             return Response({
#                 "statusCode": 400,
#                 "messages": ["Already liked"],
#                 "result": []
#             }, status=status.HTTP_400_BAD_REQUEST)
#
#         # Create Like Entry
#         CommentReplyLike.objects.create(user=user, reply=reply)
#         reply.like_count += 1
#         reply.save()
#
#         # Serialize and return updated reply
#         serializer = CommentReplySerializer(reply, context={"request": request})
#         return Response({
#             "statusCode": 200,
#             "messages": ["Like added successfully"],
#             "result": serializer.data
#         }, status=status.HTTP_200_OK)
#
#
# class ReplyUnlikeView(GenericAPIView):
#     """View to handle unliking a reply."""
#
#     @extend_schema(
#         summary="Unlike a reply",
#         description="Unlike a specific reply by providing the `reply_id` in the query parameters.",
#         parameters=[
#             OpenApiParameter(
#                 name="reply_id",
#                 description="ID of the reply to unlike",
#                 required=True,
#                 type=OpenApiTypes.INT
#             )
#         ],
#         responses={
#             200: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 200},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Like removed successfully"]
#                     },
#                     "result": {"type": "object"}  # Placeholder for serialized reply data
#                 }
#             },
#             400: {
#                 "type": "object",
#                 "properties": {
#                     "statusCode": {"type": "integer", "example": 400},
#                     "messages": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "example": ["Not liked yet", "Reply ID is required"]
#                     },
#                     "result": {}
#                 }
#             }
#         }
#     )
#     def delete(self, request):
#         """Unlike a reply by providing `reply_id` in the query parameters"""
#         user = request.user
#         reply_id = request.query_params.get("reply_id")  # ✅ Read from query parameters
#
#         if not reply_id:
#             return Response({
#                 "statusCode": 400,
#                 "messages": ["Reply ID is required"],
#                 "result": []
#             }, status=status.HTTP_400_BAD_REQUEST)
#
#         reply = get_object_or_404(CommentReply, id=reply_id)
#
#         like = CommentReplyLike.objects.filter(user=user, reply=reply).first()
#         if not like:
#             return Response({
#                 "statusCode": 400,
#                 "messages": ["Not liked yet"],
#                 "result": []
#             }, status=status.HTTP_400_BAD_REQUEST)
#
#         # Remove Like
#         like.delete()
#         reply.like_count -= 1
#         reply.save()
#
#         # Serialize and return updated reply
#         serializer = CommentReplySerializer(reply, context={"request": request})
#         return Response({
#             "statusCode": 200,
#             "messages": ["Like removed successfully"],
#             "result": serializer.data
#         }, status=status.HTTP_200_OK)


class MentionUserListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get mentionable users",
        description="Returns a flat list of users (not grouped by letter). Optional search query can filter the results.",
        parameters=[
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Optional search term to filter users by username."
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Mentionable users fetched successfully"]
                    },
                    "result": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer", "example": 12},
                                "display_username": {"type": "string", "example": "12 user"},
                                "profile_image_path": {"type": "string", "example": None}
                            }
                        }
                    }
                }
            }
        }
    )
    def get(self, request):
        search = request.query_params.get('search', None)
        users = User.objects.exclude(username__isnull=True).exclude(username__exact="")

        if search and search.strip():
            users = users.filter(username__icontains=search.strip())

        serialized_users = MentionUserSerializer(users, many=True).data

        return Response({
            "statusCode": 200,
            "messages": ["Mentionable users fetched successfully"],
            "result": serialized_users
        }, status=status.HTTP_200_OK)


class CardCommentCreatorsAPIView(ListAPIView):
    serializer_class = CommentCreatorIdSerializer
    permission_classes = []

    def get_queryset(self):
        card_id = self.kwargs.get('card_id')
        card = get_object_or_404(Card, id=card_id)
        return Comment.objects.filter(card=card).order_by('created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        total_comments_count = queryset.count()

        # Get page number and perPage from query params
        page_number = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('perPage', 20))  # default perPage to 20

        # Custom progressive pagination
        end_index = page_number * per_page
        paged_queryset = queryset[:end_index]

        serializer = self.get_serializer(paged_queryset, many=True, context={'request': request})

        return Response({
            "statusCode": 200,
            "messages": ["Comment creators retrieved successfully."],
            "total": total_comments_count,
            "page": page_number,
            "perPage": per_page,
            "result": serializer.data
        }, status=status.HTTP_200_OK)


class UserCreatedCardsAPIView(ListAPIView):
    serializer_class = CardDetailSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):
        return Card.objects.filter(creator=self.request.user).order_by('-created_at')

    @extend_schema(
        summary="Get user-created cards",
        description="Retrieve all cards created by the authenticated user, with progressive pagination.",
        parameters=[
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Page number (starts from 1)'
            ),
            OpenApiParameter(
                name='perPage',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Number of items per page (default: 20)'
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["User's created cards retrieved successfully."]
                    },
                    "total": {"type": "integer", "example": 42},
                    "page": {"type": "integer", "example": 1},
                    "perPage": {"type": "integer", "example": 20},
                    "result": {
                        "type": "array",
                        "items": {"type": "object"}  # Placeholder — your CardDetailSerializer result
                    }
                }
            }
        }
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        total_cards_count = queryset.count()

        # Get page number and perPage from query params, with defaults
        page_number = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('page_size', self.pagination_class.page_size))

        # Custom progressive pagination
        end_index = page_number * per_page
        paged_queryset = queryset[:end_index]

        serializer = self.get_serializer(paged_queryset, many=True, context={'request': request})

        return Response({
            "statusCode": 200,
            "messages": ["User's created cards retrieved successfully."],
            "total": total_cards_count,
            "page": page_number,
            "perPage": per_page,
            "result": serializer.data
        }, status=status.HTTP_200_OK)


class UserSavedCardsAPIView(ListAPIView):
    serializer_class = CardDetailSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):
        # Return Card queryset that the user saved
        saved_cards = SavedCard.objects.filter(user=self.request.user).select_related('card')
        card_ids = saved_cards.values_list('card__id', flat=True)
        return Card.objects.filter(id__in=card_ids).order_by('-created_at')

    @extend_schema(
        summary="Get user-saved cards",
        description="Retrieve all cards saved by the authenticated user, with progressive pagination.",
        parameters=[
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Page number (starts from 1)'
            ),
            OpenApiParameter(
                name='perPage',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Number of items per page (default: 20)'
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["User's saved cards retrieved successfully."]
                    },
                    "total": {"type": "integer", "example": 42},
                    "page": {"type": "integer", "example": 1},
                    "perPage": {"type": "integer", "example": 20},
                    "result": {
                        "type": "array",
                        "items": {"type": "object"}  # Placeholder — your CardDetailSerializer result
                    }
                }
            }
        }
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        total_cards_count = queryset.count()

        # Get page and perPage
        page_number = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('page_size', self.pagination_class.page_size))

        # Progressive pagination
        end_index = page_number * per_page
        paged_queryset = queryset[:end_index]

        serializer = self.get_serializer(paged_queryset, many=True, context={'request': request})

        return Response({
            "statusCode": 200,
            "messages": ["User's saved cards retrieved successfully."],
            "total": total_cards_count,
            "page": page_number,
            "perPage": per_page,
            "result": serializer.data
        }, status=status.HTTP_200_OK)


class UserProfileImageUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @extend_schema(
        summary="Update user's profile image",
        description="Update the `profile_image_path` of the authenticated user by uploading image to MinIO.",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "profile_image": {"type": "string", "format": "binary"}
                },
                "required": ["profile_image"]
            }
        },
        responses={...}  # Keep your existing response schema
    )
    def put(self, request, *args, **kwargs):
        user = request.user
        profile_image = request.FILES.get("profile_image")

        if not profile_image:
            return Response({
                "statusCode": 400,
                "messages": ["No image file provided."],
                "errors": {"profile_image": ["This field is required."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            image_path = upload_image_to_minio(profile_image, profile_image.name)
        except Exception as e:
            return Response({
                "statusCode": 500,
                "messages": ["Failed to upload image to MinIO."],
                "errors": {"minio": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = UserProfileImageUpdateSerializer(user, data={"profile_image_path": image_path}, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "statusCode": 200,
                "messages": ["Profile image updated successfully."],
                "result": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            "statusCode": 400,
            "messages": ["Invalid data."],
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class GeminiChatChallengeAPIView(APIView):
    @extend_schema(
        summary="Gemini AI Challenge Generator",
        description="ارسال پیام به مدل Gemini و دریافت فهرستی از چالش‌ها.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "example": "می‌خوام مهندس بشم"
                    }
                },
                "required": ["messages"]
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {"type": "string", "example": "موفق"},
                    "challenges": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["چالش ۱", "چالش ۲", "چالش ۳"]
                    }
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {"type": "string", "example": "message is required."}
                }
            },
            500: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 500},
                    "messages": {"type": "string", "example": "خطا: خطای پیش‌بینی نشده"}
                }
            }
        }
    )
    def post(self, request, *args, **kwargs):
        user_message = request.data.get("content")
        if not user_message:
            return Response({
                "statusCode": 400,
                "messages": "message is required."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = asyncio.run(self.handle_rag_chat(user_message))
            return Response({
                "statusCode": 200,
                "messages": "موفق",
                "result": result,
                # "response": result["response"]
            })

        except Exception as e:
            return Response({
                "statusCode": 500,
                "messages": [f"خطا: {str(e)}"],
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    async def handle_rag_chat(self, user_input):
        challenges = await rag.generate_challenges(query=user_input)
        # chosen_challenge = challenges[0]
        # response = await rag.ask_question(query=user_input, challange=chosen_challenge)
        # return {"challenges": challenges, "response": response}
        return {"response": challenges}


class GeminiChatWishAPIView(APIView):
    @extend_schema(
        summary="Gemini AI Chat",
        description="ارسال پیام به مدل Gemini و دریافت پاسخ به همراه چالش‌ها.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "string",
                        "example": "می‌خوام مهندس بشم"
                    },
                    "challange": {
                        "type": "string",
                        "example": "چالش ۱"
                    }
                },
                "required": ["messages", "challange"]
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 200},
                    "messages": {"type": "string", "example": "موفق"},
                    "response": {
                        "type": "string",
                        "example": "برای مهندس شدن باید ریاضیات و فیزیک را خوب یاد بگیری."
                    }
                }
            },
            400: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 400},
                    "messages": {"type": "string", "example": "message is required."}
                }
            },
            500: {
                "type": "object",
                "properties": {
                    "statusCode": {"type": "integer", "example": 500},
                    "messages": {"type": "string", "example": "خطا: خطای پیش‌بینی نشده"}
                }
            }
        }
    )
    def post(self, request, *args, **kwargs):
        user_message = request.data.get("messages")
        challange = request.data.get("challange")
        if not user_message:
            return Response({
                "statusCode": 400,
                "messages": "message is required."
            }, status=status.HTTP_400_BAD_REQUEST)

        if not challange:
            return Response({
                "statusCode": 400,
                "messages": "challange is required."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = asyncio.run(self.handle_rag_chat(user_message, challange))
            return Response({
                "statusCode": 200,
                "messages": "موفق",
                # "challenges": result["challenges"],
                "result": result["response"]
            })

        except Exception as e:
            return Response({
                "statusCode": 500,
                "messages": f"خطا: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    async def handle_rag_chat(self, user_input, chat_id, challange):
        # challenges = await rag.generate_challenges(query=user_input)
        # chosen_challenge = challenges[0]
        response = await rag.ask_question(query=user_input, chat_id=chat_id, challange=challange)
        # return {"challenges": challenges, "response": response}
        return {"response": response}


class NotificationView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=NotificationSerializer(many=True))
    def get(self, request):
        notifications = Notification.objects.filter(owner=request.user)
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
