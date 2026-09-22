# NCUACG/club/serializers.py
from rest_framework import serializers


class CommentCreateSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=500, trim_whitespace=True, allow_blank=False)
