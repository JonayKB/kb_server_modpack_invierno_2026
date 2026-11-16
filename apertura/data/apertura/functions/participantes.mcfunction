# Cierra la lista del sorteo: marca a todos los conectados ahora mismo,
# menos a los que tienen el rol de Discord 1251246263395946517
# (kb_discord_auth >= 1.9.0 pone a cada jugador el tag discord_role.<id> de sus roles).
# Tampoco entran quienes siguen en la sala de espera sin haber iniciado sesion con Discord.
# Uso: ejecutalo media hora antes de la apertura -> /function apertura:participantes
tag @a remove participante
execute as @a[tag=!discord_role.1251246263395946517] at @s unless dimension kb_discord_auth:limbo run tag @s add participante

scoreboard objectives add apertura dummy
execute store result score #participantes apertura if entity @a[tag=participante]

title @a[tag=participante] times 5 60 10
title @a[tag=participante] title {"text":"ESTAS DENTRO!","color":"green","bold":true}
title @a[tag=participante] subtitle {"text":"Participas en el sorteo de apertura","color":"yellow"}
execute as @a[tag=participante] at @s run playsound minecraft:entity.experience_orb.pickup master @s ~ ~ ~ 1 1

tellraw @a ["",{"text":"[SORTEO] ","color":"light_purple","bold":true},{"text":"Lista cerrada con ","color":"yellow"},{"score":{"name":"#participantes","objective":"apertura"},"color":"gold","bold":true},{"text":" participantes. Seguid conectados hasta la apertura!","color":"yellow"}]
