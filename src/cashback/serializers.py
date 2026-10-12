import re
from decimal import Decimal
from rest_framework import serializers
from .models import CashbackService, CashbackRate


class CashbackRateIngestSerializer(serializers.ModelSerializer):
    service_slug = serializers.CharField(write_only=True)

    class Meta:
        model = CashbackRate
        fields = [
            'service_slug',
            'name',
            'domain',
            'logo_url',
            'is_reg',
            'rate_text',
            'max_rate_value',
            'url'
        ]

    def create(self, validated_data):
        service_slug = validated_data.pop('service_slug')
        service = CashbackService.objects.get(slug=service_slug)
        name = validated_data.get('name')

        # Якщо max_rate_value не передали явно з парсера, пробуємо розпарсити з rate_text
        if not validated_data.get('max_rate_value') and validated_data.get('rate_text'):
            raw_text = validated_data['rate_text'].replace(',', '.')
            match = re.search(r'(\d+(?:\.\d+)?)', raw_text)
            if match:
                validated_data['max_rate_value'] = Decimal(match.group(1))

        rate_obj, _ = CashbackRate.objects.update_or_create(
            service=service,
            name=name,
            defaults=validated_data
        )
        return rate_obj