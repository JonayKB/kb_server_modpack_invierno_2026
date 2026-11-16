# Momento de la apertura: titulo, sonidos y efectos
title @a times 5 80 20
title @a title {"text":"SERVIDOR ABIERTO!","color":"green","bold":true}
title @a subtitle {"text":"Bienvenidos a MCKBServers","color":"aqua"}

execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1
execute as @a at @s run playsound minecraft:entity.firework_rocket.large_blast master @s ~ ~ ~ 1 1
execute as @a at @s run playsound minecraft:entity.firework_rocket.twinkle master @s ~ ~ ~ 1 1

execute at @a run particle minecraft:totem_of_undying ~ ~1 ~ 0.8 1 0.8 0.6 200 force
execute at @a run particle minecraft:firework ~ ~2 ~ 1.5 1.5 1.5 0.15 150 force

effect give @a minecraft:glowing 10 0 true

tellraw @a ["",{"text":"[MCKB] ","color":"gold","bold":true},{"text":"El servidor ya esta abierto! Mucha suerte a todos.","color":"green"}]

# Deja salir del lobby: quita el muro de barrera (kb_lobby:abrir, si esta el datapack del lobby)
function #apertura:abrir

# Mas cosas al abrir (descomenta y ajusta si las usas):
# gamemode survival @a[tag=!staff]
# tp @a[tag=!staff] 0 80 0
