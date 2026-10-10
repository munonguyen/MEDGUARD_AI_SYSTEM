// MedGuard Action Definition v3.0
using System;

namespace MedGuard.Doctor.Motion.Actions
{
    [Serializable]
    public class DoctorActionDefinition
    {
        public string VariantId;
        public string GroupId;
        public string ActionName;
        public string ClinicalPurpose;
        public string BodyHandMotion;
        public string FacialEyeExpression;
        public float DurationSeconds;
        public string Preconditions;
        public string Prohibitions;
    }
}
