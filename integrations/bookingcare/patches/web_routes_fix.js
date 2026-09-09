/**
 * BookingCare Patch: Fix Safety Flaw 2 (Patient Role R3 Triage Block)
 *
 * Target File: BE/src/routes/web.js
 * Vulnerable Line: ~228
 *
 * VULNERABILITY ANALYSIS:
 * In the legacy BookingCare route setup:
 *     router.use("/api/innovation", requireAuth, allowRoles("R1", "R2"));
 * was applied as blanket middleware over the entire innovation router group.
 * Consequence: Patients (role "R3") were rejected with 403 Forbidden when attempting
 * to submit symptoms for pre-consultation triage. The feature was unusable by its intended audience.
 *
 * SOLUTION:
 * 1. Remove the blanket `allowRoles("R1", "R2")` middleware from the top-level route group.
 * 2. Apply granular role gating:
 *    - Triage & Symptom Intake: allowRoles("R1", "R2", "R3")
 *    - Queue Control (call-next, complete): keep allowRoles("R1", "R2")
 */

// =========================================================================
// PATCHED ROUTE CONFIGURATION FOR BE/src/routes/web.js
// =========================================================================

function configureInnovationRoutes(router, { requireAuth, allowRoles, innovationController }) {
  // Base authentication required for all innovation routes
  const innovationRouter = router.Router ? router.Router() : router;

  // 1. PATIENT-ACCESSIBLE ROUTES (Roles: R1 - Admin, R2 - Doctor, R3 - Patient)
  // Allows patients to evaluate symptoms and fill pre-consultation intake forms
  innovationRouter.post(
    "/triage/evaluate",
    requireAuth,
    allowRoles("R1", "R2", "R3"),
    innovationController.handleEvaluateSymptoms
  );

  innovationRouter.post(
    "/triage/intake-form",
    requireAuth,
    allowRoles("R1", "R2", "R3"),
    innovationController.handleSubmitIntake
  );

  // 2. CLINICAL & ADMINISTRATIVE QUEUE ROUTES (Restricted to: R1 - Admin, R2 - Doctor)
  // Queue operations must remain restricted to healthcare providers
  innovationRouter.get(
    "/queue/status",
    requireAuth,
    allowRoles("R1", "R2"),
    innovationController.handleGetQueueStatus
  );

  innovationRouter.post(
    "/queue/call-next",
    requireAuth,
    allowRoles("R1", "R2"),
    innovationController.handleCallNextPatient
  );

  innovationRouter.post(
    "/queue/complete/:appointmentId",
    requireAuth,
    allowRoles("R1", "R2"),
    innovationController.handleCompleteConsultation
  );

  return innovationRouter;
}

module.exports = {
  configureInnovationRoutes,
};
