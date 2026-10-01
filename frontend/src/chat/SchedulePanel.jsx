import { MedicationPage } from '../schedule/MedicationPage';

export function SchedulePanel({ open, onClose, api, patientRef, onNotify }) {
  if (!open) return null;
  return <div className="drawer-layer" role="dialog" aria-modal="true" aria-label="Lịch uống thuốc">
    <button className="drawer-scrim" type="button" aria-label="Đóng lịch thuốc" onClick={onClose} />
    <aside className="schedule-drawer"><MedicationPage api={api} patientRef={patientRef} onBackToChat={onClose} onNotify={onNotify} /></aside>
  </div>;
}
