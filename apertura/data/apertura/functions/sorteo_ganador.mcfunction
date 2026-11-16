# Elige y anuncia al ganador entre los que tienen el tag "participante"
# (solo puede ganar alguien que siga conectado en el momento del sorteo)
tag @a remove ganador
tag @r[tag=participante,tag=!discord_role.1251246263395946517,gamemode=!spectator] add ganador

# Si no hay nadie valido, avisa y para
execute unless entity @a[tag=ganador] run tellraw @a ["",{"text":"[SORTEO] ","color":"light_purple","bold":true},{"text":"No hay participantes conectados para el sorteo. Usa antes /function apertura:participantes","color":"red"}]

execute if entity @a[tag=ganador] run title @a times 5 80 20
execute if entity @a[tag=ganador] run title @a title {"selector":"@a[tag=ganador]","color":"gold","bold":true}
execute if entity @a[tag=ganador] run title @a subtitle {"text":"Ha ganado el sorteo!","color":"yellow"}

execute if entity @a[tag=ganador] run tellraw @a ["",{"text":"[SORTEO] ","color":"light_purple","bold":true},{"text":"Enhorabuena a ","color":"yellow"},{"selector":"@a[tag=ganador]","color":"gold","bold":true},{"text":"! Ha ganado el rol de acceso prioritario: podra entrar aunque el servidor este lleno.","color":"yellow"}]

execute if entity @a[tag=ganador] run execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1
execute if entity @a[tag=ganador] run execute as @a at @s run playsound minecraft:entity.player.levelup master @s ~ ~ ~ 1 1
execute at @a[tag=ganador] run particle minecraft:totem_of_undying ~ ~1 ~ 0.5 1 0.5 0.5 300 force
execute at @a[tag=ganador] run particle minecraft:firework ~ ~2 ~ 1 1 1 0.1 100 force
effect give @a[tag=ganador] minecraft:glowing 30 0 true
