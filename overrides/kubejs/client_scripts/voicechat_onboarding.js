// Obliga a pasar por el asistente de configuración de Simple Voice Chat
// (micrófono, altavoz y modo de activación) en el primer arranque.
//
// De serie el mod solo avisa por chat al conectarse ("pulsa V para
// configurarlo"). Aquí se abre en la pantalla de título, antes de entrar al
// servidor, para no pisarse con los menús de dificultad y clase.
//
// Mientras no se complete, vuelve a abrirse cada vez que se llega a la
// pantalla de título. Dentro del propio asistente está la opción de saltarlo
// ("I Know What I Am Doing - Skip"), que también cuenta como completado.
// Queda guardado en config/voicechat/voicechat-client.properties
// (onboarding_finished=true); poniéndolo a false vuelve a salir.

const TitleScreen = Java.loadClass('net.minecraft.client.gui.screens.TitleScreen')
const OnboardingManager = Java.loadClass('de.maxhenkel.voicechat.gui.onboarding.OnboardingManager')

let lastScreen = null

ClientEvents.tick(event => {
    const screen = Client.screen
    if (screen === lastScreen) return
    lastScreen = screen

    if (!(screen instanceof TitleScreen)) return
    try {
        if (OnboardingManager.isOnboarding()) {
            Client.setScreen(OnboardingManager.getOnboardingScreen(screen))
        }
    } catch (e) {
        console.error('No se pudo abrir el asistente de Voice Chat: ' + e)
    }
})
