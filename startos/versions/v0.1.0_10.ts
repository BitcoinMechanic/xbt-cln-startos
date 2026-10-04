import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const v_0_1_0_10 = VersionInfo.of({
  version: '0.1.0:10',
  releaseNotes: {
    en_US:
      'Adds bounded Lightning invoices, reviewed payments and durable payment status without automatic resubmission',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
