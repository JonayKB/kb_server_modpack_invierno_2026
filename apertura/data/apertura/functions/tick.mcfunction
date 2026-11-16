# Un paso de la cuenta atras (se llama cada segundo)
title @a times 0 25 0

# 10 a 4: numeros dorados
execute if score #t apertura matches 4.. run title @a title {"score":{"name":"#t","objective":"apertura"},"color":"gold","bold":true}
execute if score #t apertura matches 4.. as @a at @s run playsound minecraft:block.note_block.pling master @s ~ ~ ~ 1 1

# 3, 2, 1: numeros rojos, sonido mas agudo y particulas
execute if score #t apertura matches 1..3 run title @a title {"score":{"name":"#t","objective":"apertura"},"color":"red","bold":true}
execute if score #t apertura matches 1..3 as @a at @s run playsound minecraft:block.note_block.pling master @s ~ ~ ~ 1 2
execute if score #t apertura matches 1..3 at @a run particle minecraft:flame ~ ~1 ~ 0.6 0.6 0.6 0.02 40 force

execute if score #t apertura matches 1.. run title @a subtitle {"text":""}
execute if score #t apertura matches 1.. run title @a actionbar {"text":"Apertura de MCKBServers","color":"aqua"}

# 0: gran final
execute if score #t apertura matches 0 run function apertura:final

scoreboard players remove #t apertura 1
execute if score #t apertura matches 0.. run schedule function apertura:tick 1s
