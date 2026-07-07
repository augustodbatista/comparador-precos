import { Capacitor } from '@capacitor/core'
import { Haptics, ImpactStyle, NotificationType } from '@capacitor/haptics'

export async function tapFeedback(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return
  await Haptics.impact({ style: ImpactStyle.Light }).catch(() => undefined)
}

export async function successFeedback(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return
  await Haptics.notification({ type: NotificationType.Success }).catch(() => undefined)
}

export async function errorFeedback(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return
  await Haptics.notification({ type: NotificationType.Error }).catch(() => undefined)
}
