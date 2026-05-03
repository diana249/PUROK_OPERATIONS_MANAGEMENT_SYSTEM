from rest_framework import serializers

from management.models import Attendance, Fee, PurokClearance, Resident


class ResidentSerializer(serializers.ModelSerializer):
    purok_name = serializers.CharField(source="purok.name", read_only=True)

    class Meta:
        model = Resident
        fields = [
            "id",
            "first_name",
            "last_name",
            "purok",
            "purok_name",
            "barangay",
            "city",
            "province",
            "date_of_birth",
            "contact_number",
        ]


class AttendanceSerializer(serializers.ModelSerializer):
    resident_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = ["id", "resident", "resident_name", "date", "status"]

    def get_resident_name(self, obj):
        return str(obj.resident)


class FeeSerializer(serializers.ModelSerializer):
    resident_name = serializers.SerializerMethodField()
    fee_type_name = serializers.CharField(source="fee_type.name", read_only=True)

    class Meta:
        model = Fee
        fields = ["id", "resident", "resident_name", "amount", "fee_type", "fee_type_name", "paid", "date_paid", "created_at"]

    def get_resident_name(self, obj):
        return str(obj.resident)


class ClearanceSerializer(serializers.ModelSerializer):
    resident_name = serializers.SerializerMethodField()
    clearance_type_name = serializers.CharField(source="clearance_type.name", read_only=True)

    class Meta:
        model = PurokClearance
        fields = ["id", "resident", "resident_name", "clearance_type", "clearance_type_name", "date_issued", "remarks"]

    def get_resident_name(self, obj):
        return str(obj.resident)


class DashboardSummarySerializer(serializers.Serializer):
    total_residents = serializers.IntegerField()
    total_attendance = serializers.IntegerField()
    unpaid_fees = serializers.IntegerField()
    clearances_issued = serializers.IntegerField()
