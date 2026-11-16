# Sorteo entre los participantes conectados (ver apertura:participantes)
# Uso: /function apertura:sorteo
tag @a remove ganador

title @a times 5 60 10
title @a title {"text":"SORTEO","color":"light_purple","bold":true}
title @a subtitle {"text":"Eligiendo ganador...","color":"yellow"}
execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 1 1
execute as @a at @s run playsound minecraft:block.beacon.power_select master @s ~ ~ ~ 1 1

schedule function apertura:sorteo_ganador 4s
