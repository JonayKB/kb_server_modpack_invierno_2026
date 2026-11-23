// Obliga a pasar por el asistente de configuración de Simple Voice Chat
// (micrófono, altavoz y modo de activación) la primera vez que se entra.
//
// De serie el mod solo avisa por chat al conectarse ("pulsa V para
// configurarlo"). Aquí se abre dentro del servidor, pero solo después de todas
// las pantallas de entrada: login de Discord (KB Discord Auth), dificultad
// (difficulty_enhancement), clase (class_enhancement) y bienvenida. Para eso
// espera a que el jugador tenga clase (el servidor la sincroniza al entrar, o
// al elegirla) y lleve unos segundos jugando sin ninguna pantalla abierta.
//
// Mientras no se complete, vuelve a salir en cada conexión. Dentro del propio
// asistente está la opción de saltarlo ("I Know What I Am Doing - Skip"), que
// también cuenta como completado. Queda guardado en
// config/voicechat/voicechat-client.properties (onboarding_finished=true);
// poniéndolo a false vuelve a salir.

const OnboardingManager = Java.loadClass('de.maxhenkel.voicechat.gui.onboarding.OnboardingManager')
const ClassAccess = Java.loadClass('com.misanthropy.linggango.class_enhancement.client.ClientAccess')

// Ticks seguidos sin pantallas antes de abrirlo (20 = 1 s). Da margen a que
// el servidor abra la siguiente pantalla de la cadena.
const IDLE_TICKS = 60

let idleTicks = 0
let done = false

ClientEvents.loggedIn(event => {
    idleTicks = 0
    done = false
})

ClientEvents.tick(event => {
    if (done) return
    if (Client.screen != null || ClassAccess.clientClassId == null) {
        idleTicks = 0
        return
    }
    if (++idleTicks < IDLE_TICKS) return

    done = true
    try {
        if (OnboardingManager.isOnboarding()) {
            console.info('[voicechat_onboarding] Abriendo el asistente de Voice Chat')
            Client.setScreen(OnboardingManager.getOnboardingScreen(null))
        }
    } catch (e) {
        console.error('No se pudo abrir el asistente de Voice Chat: ' + e)
    }
})
