from rest_framework import serializers
from .models import (User, Card, Notification, Comment,
                     CommentReply, SavedCard, CommentLike,
                     CommentReplyLike)


class LoginSerializer(serializers.Serializer):
    mobile_phone_number = serializers.CharField(max_length=12)

    def validate_mobile_phone_number(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Mobile phone number must be numeric.")
        return value

class OTPLoginSerializer(serializers.Serializer):
    mobile_phone_number = serializers.CharField(max_length=12)
    otp = serializers.CharField(max_length=5, min_length=5, write_only=True)

    def validate_mobile_phone_number(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Mobile phone number must be numeric.")
        return value

    # def validate_otp(self, value):
    #     mobile_phone_number = self.initial_data.get('mobile_phone_number')
    #     cache_key = f"otp:{mobile_phone_number}"
    #     cached_otp = cache.get(cache_key)
    #
    #     if not cached_otp:
    #         raise serializers.ValidationError("OTP has expired or was not generated.")
    #     if cached_otp != value:
    #         raise serializers.ValidationError("Invalid OTP provided.")
    #
    #     cache.delete(cache_key)
    #     return value

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'mobile_phone_number', 'username', 'Full_name', 'bio', 'profile_image_path',
                  'is_block', 'which_social_media', 'chat_id', 'is_admin', 'premium_level', 'subscription_end']

class UserRegistrationSerializer(serializers.ModelSerializer):
    mobile_phone_number = serializers.CharField()
    username = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ['mobile_phone_number', 'username', 'full_name', 'bio']

    def validate_mobile_phone_number(self, value):
        user = self.instance
        queryset = User.objects.filter(mobile_phone_number=value)
        if user:
            queryset = queryset.exclude(pk=user.pk)
        if queryset.exists():
            raise serializers.ValidationError("This mobile number is already in use.")
        return value

    def create(self, validated_data):
        user = User.objects.create(**validated_data)
        return user

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class CommentSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    # parent = serializers.PrimaryKeyRelatedField(queryset=Comment.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Comment
        fields = ['id', 'content', 'card', 'creator', 'created_at', 'updated_at', 'like_count']
        read_only_fields = ['like_count']
        # read_only_fields = ['parent']  # Make parent read-only during updates

    def get_creator(self, obj):
        """
        Return the username if it exists, otherwise return the phone number.
        """
        if obj.creator and obj.creator.username:
            return obj.creator.username
        elif obj.creator and obj.creator.id:
            return obj.creator.id
        else:
            return "No Username or Phone"  # Or some default value/message

    def create(self, validated_data):
        card = validated_data.get('card')
        # parent = validated_data.pop('parent', None)  # Get parent from validated data, remove it, default to None
        #
        # if parent is None:
        #     # Find the most recent comment for this card
        #     last_comment = Comment.objects.filter(card=card).order_by('-created_at').first()
        #     if last_comment:
        #         parent = last_comment

        validated_data['creator'] = self.context['request'].user
        comment = Comment.objects.create(**validated_data)#, parent=parent)  # Create the comment with the determined parent
        return comment

    def get_is_liked(self, obj):
        """Check if the authenticated user has liked this comment"""
        user = self.context.get('request').user
        if user.is_authenticated:
            return CommentLike.objects.filter(user=user, comment=obj).exists()
        return False

class CommentReplySerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    created_at = serializers.ReadOnlyField()

    class Meta:
        model = CommentReply
        fields = ['id', 'comment', 'user', 'content', 'created_at', 'like_count']
        read_only_fields = ['like_count']

    def get_user(self, obj):
        """
        Return the username if available, otherwise return the user id.
        """
        if obj.user and obj.user.username:
            return obj.user.username
        return obj.user.id

    def get_is_liked(self, obj):
        """Check if the authenticated user has liked this reply"""
        user = self.context.get('request').user
        if user.is_authenticated:
            return CommentReplyLike.objects.filter(user=user, reply=obj).exists()
        return False

class CommentWithRepliesSerializer(CommentSerializer):
    # The "replies" field will use the related name defined on CommentReply (e.g., related_name='replies')
    replies = CommentReplySerializer(many=True, read_only=True)

    class Meta(CommentSerializer.Meta):
        # Include all fields from CommentSerializer plus replies
        fields = CommentSerializer.Meta.fields + ['replies']

class SavedCardSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    card = serializers.StringRelatedField(read_only=True)
    card_id = serializers.PrimaryKeyRelatedField(
        queryset=Card.objects.all(), source='card', write_only=True
    )

    class Meta:
        model = SavedCard
        fields = ['id', 'user', 'card', 'card_id', 'saved_at']
        read_only_fields = ['id', 'user', 'card', 'saved_at']

class CardSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()  # ✅ Add is_saved

    class Meta:
        model = Card
        fields = ['id', 'content', 'challenge', 'creator', 'created_at', 'like_count', 'is_saved']

    def get_creator(self, obj):
        return obj.creator.username if obj.creator.username else obj.creator.id

    def get_is_saved(self, obj):
        """Check if the authenticated user has saved the card."""
        request = self.context.get('request')  # Get the request from the context
        if request and request.user.is_authenticated:
            return SavedCard.objects.filter(user=request.user, card=obj).exists()
        return False  # Default to False for unauthenticated users

class NotificationSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    related_entity = CardSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'owner', 'title', 'message', 'created_at', 'related_entity']

# class CommentReplySerializer(serializers.ModelSerializer):
#     is_liked = serializers.SerializerMethodField()
#
#     class Meta:
#         model = CommentReply
#         fields = ['id', 'content', 'like_count', 'is_liked', 'comment', 'user']
#         extra_kwargs = {
#             'comment': {'write_only': True},  # Allow comment to be set, but not returned
#             'user': {'read_only': True}       # Set automatically when creating
#         }
#
#     def get_is_liked(self, obj):
#         """Check if the authenticated user has liked this reply"""
#         user = self.context.get('request').user
#         if user.is_authenticated:
#             return CommentReplyLike.objects.filter(user=user, reply=obj).exists()
#         return False


# class LoginSerializer(serializers.Serializer):
#     mobile_phone_number = serializers.CharField(max_length=15)
#
#     def validate_mobile_phone_number(self, value):
#         """Validate that the mobile phone number contains only digits."""
#         if not value.isdigit():
#             raise serializers.ValidationError("Mobile phone number must be numeric.")
#         return value
#
#
# class OTPLoginSerializer(serializers.Serializer):
#     mobile_phone_number = serializers.CharField(max_length=15)
#     otp = serializers.CharField(max_length=5, min_length=5, write_only=True)  # This hides the OTP field from Swagger
#
#     def validate_mobile_phone_number(self, value):
#         """Validate that the mobile phone number contains only digits."""
#         if not value.isdigit():
#             raise serializers.ValidationError("Mobile phone number must be numeric.")
#         return value
#
#     def validate_otp(self, value):
#         """Validate the OTP entered by the user."""
#         mobile_phone_number = self.initial_data.get('mobile_phone_number')
#         cache_key = f"otp:{mobile_phone_number}"
#
#         # Get OTP from the cache
#         cached_otp = cache.get(cache_key)
#
#         if not cached_otp:
#             raise serializers.ValidationError("OTP has expired or was not generated.")
#
#         if cached_otp != value:
#             raise serializers.ValidationError("Invalid OTP provided.")
#
#         # OTP is valid, remove it from cache after successful validation
#         cache.delete(cache_key)
#         return value
#
# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ['id', 'mobile_phone_number', 'first_name', 'last_name', 'bio', 'profile_image_path']
#
#     def create(self, validated_data):
#         # Use the custom method to get or create the user
#         user, created = self.get_or_create_user(validated_data)
#         return user, created
#
#     def get_or_create_user(self, validated_data):
#         """
#         Custom method to get or create a user based on mobile phone number.
#         Returns the user object and a boolean indicating whether the user was created.
#         """
#         user = User.objects.filter(mobile_phone_number=validated_data['mobile_phone_number']).first()
#         if user:
#             return user, False  # If user exists, return the user and created flag as False
#         else:
#             # If user does not exist, create a new one
#             user = User.objects.create(**validated_data)
#             return user, True  # Return the new user and created flag as True
#
# class UserRegistrationSerializer(serializers.ModelSerializer):
#     mobile_phone_number = serializers.CharField()
#
#     class Meta:
#         model = User
#         fields = ['mobile_phone_number', 'first_name', 'last_name', 'bio']
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # Make mobile_phone_number optional during updates
#         if self.instance is not None:
#             self.fields['mobile_phone_number'].required = False
#
#     def validate_mobile_phone_number(self, value):
#         # Check uniqueness, excluding the current user during updates
#         user = self.instance  # `self.instance` exists during updates
#         queryset = User.objects.filter(mobile_phone_number=value)
#         if user:
#             queryset = queryset.exclude(pk=user.pk)  # Exclude current user
#         if queryset.exists():
#             raise serializers.ValidationError("This mobile number is already in use.")
#         return value
#
#     def create(self, validated_data):
#         # Create a new user (mobile_phone_number is validated as unique)
#         user = User.objects.create(
#             mobile_phone_number=validated_data['mobile_phone_number'],
#             first_name=validated_data.get('first_name', ''),
#             last_name=validated_data.get('last_name', ''),
#             bio=validated_data.get('bio', '')
#         )
#         return user
#
#     def update(self, instance, validated_data):
#         # Update mobile_phone_number if provided
#         if 'mobile_phone_number' in validated_data:
#             instance.mobile_phone_number = validated_data['mobile_phone_number']
#         if 'first_name' in validated_data:
#             instance.first_name = validated_data['first_name']
#         if 'last_name' in validated_data:
#             instance.last_name = validated_data['last_name']
#         if 'bio' in validated_data:
#             instance.bio = validated_data['bio']
#         instance.save()
#         return instance
#
# class FCMTokenSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = FCMToken
#         fields = ['id', 'user', 'fcm_token', 'device_type']
#
#     def create(self, validated_data):
#         # You can modify the creation of the FCM token here if you want to handle refresh tokens in a specific way
#         fcm_token = FCMToken.objects.create(**validated_data)
#         return fcm_token
#
#
# class RefreshTokenSerializer(serializers.Serializer):
#     refresh_token = serializers.CharField()
#
#     def validate_refresh_token(self, value):
#         # Validate the refresh token if necessary (check against DB or token validity)
#         return value
#
#     def create(self, validated_data):
#         refresh_token = validated_data.get('refresh_token')
#         refresh = RefreshToken(refresh_token)
#         access_token = str(refresh.access_token)  # Generate new access token from refresh token
#
#         return {"access_token": access_token, "refresh_token": str(refresh)}


# class LoginSerializer(serializers.Serializer):
#     mobile_phone_number = serializers.CharField()
#
#     def validate(self, data):
#         mobile_phone_number = data.get("mobile_phone_number")
#
#         try:
#             user = User.objects.get(mobile_phone_number=mobile_phone_number)
#         except User.DoesNotExist:
#             raise serializers.ValidationError("User with this phone number does not exist.")
#
#         data["user"] = user
#         return data
