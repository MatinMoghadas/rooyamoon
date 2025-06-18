from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OTPLoginView, OTPVerificationView, UserProfileView,
    NotificationView, CardViewSet, CommentViewSet,
    CustomTokenRefreshView, SavedCardAPIView,
    SavedCardDeleteAPIView, CommentLikeView,
    CommentUnlikeView, UpdateCommentView,
    MentionUserListAPIView, CardCommentsRepliesAPIView,
    GeminiChatChallengeAPIView, GeminiChatWishAPIView,
    CardCommentCreatorsAPIView, UserCreatedCardsAPIView,
    UserSavedCardsAPIView, UserProfileImageUpdateAPIView,
    GeminiSuggestAPIView
    # CommentReplyViewSet, CardCommentsRepliesAPIView, CommentReplyUpdateViewSet,
    # CommentReplyLikeView, ReplyUnlikeView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

router = DefaultRouter()
router.register(r'cards', CardViewSet, basename='card')
router.register(r'comments', CommentViewSet, basename='comment')
# router.register(r'comment-replies', CommentReplyViewSet)


urlpatterns = [
    path('api/mentions/', MentionUserListAPIView.as_view(), name='mention-users'),
    path("api/comments/update/", UpdateCommentView.as_view(), name="update-comment"),
    path('api/comments/like/', CommentLikeView.as_view(), name='comment-like'),
    path('api/comments/unlike/', CommentUnlikeView.as_view(), name='comment-unlike'),
    path('api/saved-cards/', SavedCardAPIView.as_view(), name='saved-cards'),
    path('api/saved-cards/<int:card_id>/', SavedCardDeleteAPIView.as_view(), name='delete-saved-card'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path("api/chat/challenge", GeminiChatChallengeAPIView.as_view(), name="gemini-chat-challenge"),
    path("api/chat/wish", GeminiChatWishAPIView.as_view(), name="gemini-chat-wish"),
    path('api/gemini/suggest/', GeminiSuggestAPIView.as_view(), name='gemini-suggest'),
    path("auth/login/", OTPLoginView.as_view(), name="otp-login"),
    path("auth/verify/", OTPVerificationView.as_view(), name="otp-verify"),
    path("user/profile/", UserProfileView.as_view(), name="user-profile"),
    path('user/me/cards/', UserCreatedCardsAPIView.as_view(), name='user-created-cards'),
    path('user/me/saved-cards/', UserSavedCardsAPIView.as_view(), name='user-saved-cards'),
    path('user/me/profile-image/', UserProfileImageUpdateAPIView.as_view(), name='user-profile-image-update'),
    path('api/', include(router.urls)),
    path("notifications/", NotificationView.as_view(), name="notifications"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path('api/cards/<int:card_id>/comment-creators/', CardCommentCreatorsAPIView.as_view(), name='card-comment-creators'),
    path('api/cards/<int:card_id>/comments/', CardCommentsRepliesAPIView.as_view(),
         name='card-comments-replies'),

    # path('api/replies/like/', CommentReplyLikeView.as_view(), name='reply-like'),
    # path('api/replies/unlike/', ReplyUnlikeView.as_view(), name='reply-unlike'),
    # path('api/replies', CommentReplyUpdateViewSet.as_view(), name='comment-reply-update'),
    # path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
]


# from django.urls import path, re_path
# from drf_spectacular.views import (
#     SpectacularAPIView,
#     SpectacularRedocView,
#     SpectacularSwaggerView,
# )
# from .views import (
#     OTPLoginView,
#     RefreshTokenView,
#     AuthenticateUserView,
#     OTPVerificationView,
#     UpdateUserView
# )
#
# urlpatterns = [
#     path("login/", OTPLoginView.as_view(), name="otp-login"),
#     path("refresh-token/", RefreshTokenView.as_view(), name="refresh-token"),
#     # path("change_profile/", AuthenticateUserView.as_view(), name="register"),
#     path("verify-otp/", OTPVerificationView.as_view(), name="verify-otp"),
#     path("update-user/", UpdateUserView.as_view(), name="update-user"),
#     path("schema/", SpectacularAPIView.as_view(), name="schema"),
#     path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
#     path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
#     path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
# ]
