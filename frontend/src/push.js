let initialized;
export function initPush(appId) {
  if (!appId)
    return Promise.reject(
      new Error("Configure ONESIGNAL_APP_ID on the backend first."),
    );
  if (initialized) return initialized;
  initialized = new Promise((resolve, reject) => {
    const timer = setTimeout(
      () =>
        reject(
          new Error(
            "OneSignal did not load. Check your connection and browser content blockers.",
          ),
        ),
      15000,
    );
    window.OneSignalDeferred = window.OneSignalDeferred || [];
    window.OneSignalDeferred.push(async (OneSignal) => {
      try {
        await OneSignal.init({
          appId,
          allowLocalhostAsSecureOrigin: true,
          serviceWorkerPath: "/OneSignalSDKWorker.js",
          notifyButton: { enable: false },
          welcomeNotification: { disable: true },
          promptOptions: {
            slidedown: { prompts: [{ type: "push", autoPrompt: false }] },
          },
        });
        clearTimeout(timer);
        resolve(OneSignal);
      } catch (error) {
        clearTimeout(timer);
        reject(error);
      }
    });
    const script = document.createElement("script");
    script.src = "https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js";
    script.defer = true;
    script.onerror = () => {
      clearTimeout(timer);
      reject(new Error("Could not load OneSignal."));
    };
    document.head.appendChild(script);
  });
  return initialized;
}
export async function subscribe(appId) {
  const os = await initPush(appId);
  if (!os.Notifications.isPushSupported())
    throw new Error("This browser does not support Web Push.");
  await os.Notifications.requestPermission();
  if (!os.Notifications.permission)
    throw new Error(
      "Notification permission was not granted. Enable it in browser site settings.",
    );
  await os.User.PushSubscription.optIn();
  if (os.User.PushSubscription.id) return os.User.PushSubscription.id;
  return new Promise((resolve, reject) => {
    const listener = (event) => {
      if (event.current.id && event.current.optedIn) {
        cleanup();
        resolve(event.current.id);
      }
    };
    const timer = setTimeout(() => {
      cleanup();
      reject(
        new Error("Subscription is still registering. Try Subscribe again."),
      );
    }, 15000);
    const cleanup = () => {
      clearTimeout(timer);
      os.User.PushSubscription.removeEventListener("change", listener);
    };
    os.User.PushSubscription.addEventListener("change", listener);
  });
}
