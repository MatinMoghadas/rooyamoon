from rest_framework import serializers
from .models import (User, Card, Notification, Comment,
                     #CommentReply,
                     SavedCard, CommentLike,
                     #CommentReplyLike
                     )
from .utils import get_display_username, extract_mentions


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
        fields = '__all__'  # or list specific fields if needed

    # def save(self, **kwargs):
    #     instance = super().save(**kwargs)
    #
    #     # Automatically assign username if missing
    #     if not instance.username:
    #         instance.username = f"{instance.id}user"
    #         instance.save(update_fields=['username'])
    #
    #     return instance

    def create(self, validated_data):
        if not validated_data.get('username'):
            # Create user first so ID is available
            user = User.objects.create(**validated_data)
            user.username = f"{user.id}user"
            user.save()
            return user
        return User.objects.create(**validated_data)

    def get_display_username(self, obj):
        return get_display_username(obj)


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
        username = validated_data.get('username')
        if not username:
            # Temporarily remove it to allow creation without it (since it's unique)
            validated_data.pop('username', None)

        user = User.objects.create(**validated_data)

        # Now that user.id exists, set the username if it was not provided
        if not username:
            user.username = f"user{user.id}_{user.mobile_phone_number}"
            user.save(update_fields=['username'])

        return user

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class CommentSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    mentions = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), many=True, required=False
    )

    class Meta:
        model = Comment
        fields = '__all__'
        read_only_fields = ['creator', 'like_count']

    def get_creator(self, obj):
        return obj.creator.username if obj.creator else None

    def to_representation(self, instance):
        """Customize output to show usernames for mentions"""
        representation = super().to_representation(instance)
        representation['mentions'] = [user.username for user in instance.mentions.all()]
        return representation

    def create(self, validated_data):
        user = self.context['request'].user
        mentions = validated_data.pop('mentions', [])
        comment = Comment.objects.create(creator=user, **validated_data)
        if mentions:
            comment.mentions.set(mentions)
        return comment

    def update(self, instance, validated_data):
        mentions = validated_data.pop('mentions', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if mentions is not None:
            instance.mentions.set(mentions)

        return instance


class CommentWithRepliesCreatorSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    mentionedUserIds = serializers.SerializerMethodField()
    parentId = serializers.SerializerMethodField()
    createdAt = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id',
            'creator',
            'content',
            'mentionedUserIds',
            'parentId',
            'createdAt',
            'replies',
        ]

    def get_creator(self, obj):
        return f"u{obj.creator.id}"

    def get_mentionedUserIds(self, obj):
        return [f"u{user.id}" for user in obj.mentions.all()]

    def get_parentId(self, obj):
        return f"c{obj.parent.id}" if obj.parent else None

    def get_createdAt(self, obj):
        return obj.created_at.isoformat()

    def get_replies(self, obj):
        children = obj.replies.all()
        return CommentWithRepliesCreatorSerializer(children, many=True, context=self.context).data


# class CommentReplySerializer(serializers.ModelSerializer):
#     user = serializers.SerializerMethodField()
#     created_at = serializers.ReadOnlyField()
#     parent_reply = serializers.PrimaryKeyRelatedField(
#         queryset=CommentReply.objects.all(), required=False, allow_null=True
#     )
#     is_liked = serializers.SerializerMethodField()  # Don't forget to add this to fields if you're using it.
#
#     class Meta:
#         model = CommentReply
#         fields = [
#             'id',
#             'comment',
#             'user',
#             'content',
#             'created_at',
#             'like_count',
#             'parent_reply',
#             'is_liked'
#         ]
#         read_only_fields = ['like_count', 'created_at']
#
#     def get_user(self, obj):
#         """
#         Return the username if available, otherwise return the user id.
#         """
#         if obj.user and obj.user.username:
#             return obj.user.username
#         return obj.user.id
#
#     def get_is_liked(self, obj):
#         """
#         Check if the authenticated user has liked this reply.
#         """
#         user = self.context.get('request').user
#         if user.is_authenticated:
#             return CommentReplyLike.objects.filter(user=user, reply=obj).exists()
#         return False


# class CommentWithRepliesCreatorSerializer(serializers.ModelSerializer):
#     creator = serializers.SerializerMethodField()
#     created_at = serializers.ReadOnlyField()
#     updated_at = serializers.ReadOnlyField()
#     replies = serializers.SerializerMethodField()
#
#     class InlineReplySerializer(serializers.ModelSerializer):
#         creator = serializers.SerializerMethodField()
#         created_at = serializers.ReadOnlyField()
#         parent_reply = serializers.PrimaryKeyRelatedField(read_only=True)
#         child_replies = serializers.SerializerMethodField()
#
#         class Meta:
#             model = CommentReply
#             fields = [
#                 'id',
#                 'comment',
#                 'creator',
#                 'content',
#                 'created_at',
#                 'like_count',
#                 'parent_reply',
#                 'child_replies'
#             ]
#
#         def get_creator(self, obj):
#             return obj.user.username if obj.user and obj.user.username else obj.user.id
#
#         def get_child_replies(self, obj):
#             children = obj.child_replies.all()
#             serializer = self.__class__(children, many=True, context=self.context)
#             return serializer.data
#
#     def get_creator(self, obj):
#         # FIXED: Changed from obj.user to obj.creator
#         return obj.creator.username if obj.creator and obj.creator.username else obj.creator.id
#
#     def get_replies(self, obj):
#         top_level_replies = obj.replies.filter(parent_reply__isnull=True)
#         serializer = self.InlineReplySerializer(top_level_replies, many=True, context=self.context)
#         return serializer.data
#
#     class Meta:
#         model = Comment
#         fields = [
#             'id',
#             'content',
#             'card',
#             'creator',
#             'created_at',
#             'updated_at',
#             'like_count',
#             'replies'
#         ]


# class CommentWithRepliesSerializer(CommentSerializer):
#     # The "replies" field will use the related name defined on CommentReply (e.g., related_name='replies')
#     replies = CommentReplySerializer(many=True, read_only=True)
#
#     class Meta(CommentSerializer.Meta):
#         # Include all fields from CommentSerializer plus replies
#         fields = CommentSerializer.Meta.fields + ['replies']


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


class MentionUserSerializer(serializers.ModelSerializer):
    display_username = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'display_username', 'profile_image_path']

    def get_display_username(self, obj):
        return get_display_username(obj)


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
