set_db timing_enable_simultaneous_setup_hold_mode false
# htree4 logical changes: Innovus script, source it to reproduce them.

# ============================================================
# Step 1: Create all nets
# ============================================================

# spine mgt_clk_main: root net
create_net -name mgt_clk_main_primary_input
create_net -name mgt_clk_main_L1_inv1_Y
create_net -name mgt_clk_main_L1_inv2_Y
create_net -name mgt_clk_main_L1_inv3_Y
create_net -name mgt_clk_main_L2_inv1_Y
create_net -name mgt_clk_main_L3_inv1_Y
create_net -name mgt_clk_main_L3_inv2_Y
create_net -name mgt_clk_main_L4_inv1_Y
create_net -name mgt_clk_main_L4_inv2_Y
create_net -name mgt_clk_main_L4_inv3_Y
create_net -name mgt_clk_main_L4_inv4_Y
create_net -name mgt_clk_main_mirror_L1_inv1_Y
create_net -name mgt_clk_main_mirror_L1_inv2_Y
create_net -name mgt_clk_main_mirror_L1_inv3_Y
create_net -name mgt_clk_main_mirror_L2_inv1_Y
create_net -name mgt_clk_main_mirror_L3_inv1_Y
create_net -name mgt_clk_main_mirror_L3_inv2_Y
create_net -name mgt_clk_main_mirror_L4_inv1_Y
create_net -name mgt_clk_main_mirror_L4_inv2_Y
create_net -name mgt_clk_main_mirror_L4_inv3_Y
create_net -name mgt_clk_main_mirror_L4_inv4_Y

# spine mgt_clk_clk_spine_bot: root net
create_net -name mgt_clk_clk_spine_bot_primary_input
create_net -name mgt_clk_clk_spine_bot_L1_inv1_Y
create_net -name mgt_clk_clk_spine_bot_L2_inv1_Y
create_net -name mgt_clk_clk_spine_bot_L3_inv1_Y
create_net -name mgt_clk_clk_spine_bot_L3_inv2_Y
create_net -name mgt_clk_clk_spine_bot_mirror_L1_inv1_Y
create_net -name mgt_clk_clk_spine_bot_mirror_L2_inv1_Y
create_net -name mgt_clk_clk_spine_bot_mirror_L3_inv1_Y
create_net -name mgt_clk_clk_spine_bot_mirror_L3_inv2_Y

# spine mgt_clk_clk_spine_top: root net
create_net -name mgt_clk_clk_spine_top_primary_input
create_net -name mgt_clk_clk_spine_top_L1_inv1_Y
create_net -name mgt_clk_clk_spine_top_L2_inv1_Y
create_net -name mgt_clk_clk_spine_top_L3_inv1_Y
create_net -name mgt_clk_clk_spine_top_L3_inv2_Y
create_net -name mgt_clk_clk_spine_top_mirror_L1_inv1_Y
create_net -name mgt_clk_clk_spine_top_mirror_L2_inv1_Y
create_net -name mgt_clk_clk_spine_top_mirror_L3_inv1_Y
create_net -name mgt_clk_clk_spine_top_mirror_L3_inv2_Y

# spine soc_clk_main: root net
create_net -name soc_clk_main_primary_input
create_net -name soc_clk_main_L1_inv1_Y
create_net -name soc_clk_main_L1_inv2_Y
create_net -name soc_clk_main_L1_inv3_Y
create_net -name soc_clk_main_L2_inv1_Y
create_net -name soc_clk_main_L3_inv1_Y
create_net -name soc_clk_main_L3_inv2_Y
create_net -name soc_clk_main_L4_inv1_Y
create_net -name soc_clk_main_L4_inv2_Y
create_net -name soc_clk_main_L4_inv3_Y
create_net -name soc_clk_main_L4_inv4_Y
create_net -name soc_clk_main_mirror_L1_inv1_Y
create_net -name soc_clk_main_mirror_L1_inv2_Y
create_net -name soc_clk_main_mirror_L1_inv3_Y
create_net -name soc_clk_main_mirror_L2_inv1_Y
create_net -name soc_clk_main_mirror_L3_inv1_Y
create_net -name soc_clk_main_mirror_L3_inv2_Y
create_net -name soc_clk_main_mirror_L4_inv1_Y
create_net -name soc_clk_main_mirror_L4_inv2_Y
create_net -name soc_clk_main_mirror_L4_inv3_Y
create_net -name soc_clk_main_mirror_L4_inv4_Y

# spine soc_clk_bot: root net
create_net -name soc_clk_bot_primary_input
create_net -name soc_clk_bot_L1_inv1_Y
create_net -name soc_clk_bot_L2_inv1_Y
create_net -name soc_clk_bot_L3_inv1_Y
create_net -name soc_clk_bot_L3_inv2_Y
create_net -name soc_clk_bot_mirror_L1_inv1_Y
create_net -name soc_clk_bot_mirror_L2_inv1_Y
create_net -name soc_clk_bot_mirror_L3_inv1_Y
create_net -name soc_clk_bot_mirror_L3_inv2_Y

# spine soc_clk_top: root net
create_net -name soc_clk_top_primary_input
create_net -name soc_clk_top_L1_inv1_Y
create_net -name soc_clk_top_L2_inv1_Y
create_net -name soc_clk_top_L3_inv1_Y
create_net -name soc_clk_top_L3_inv2_Y
create_net -name soc_clk_top_mirror_L1_inv1_Y
create_net -name soc_clk_top_mirror_L2_inv1_Y
create_net -name soc_clk_top_mirror_L3_inv1_Y
create_net -name soc_clk_top_mirror_L3_inv2_Y

# ============================================================
# Step 2: Place and connect spine mgt_clk_main level L1
# ============================================================

# mgt_clk_main_L1_inv1  lower-left (5695.32, 5640.86) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_L1_inv1
place_inst mgt_clk_main_L1_inv1 5695.32 5640.86 R0
set_db inst:mgt_clk_main_L1_inv1 .place_status fixed
connect mgt_clk_main_L1_inv1/A -net mgt_clk_main_primary_input
connect mgt_clk_main_L1_inv1/Y -net mgt_clk_main_L1_inv1_Y

# mgt_clk_main_L1_inv2  lower-left (5695.32, 6841.01) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_L1_inv2
place_inst mgt_clk_main_L1_inv2 5695.32 6841.01 MX
set_db inst:mgt_clk_main_L1_inv2 .place_status fixed
connect mgt_clk_main_L1_inv2/A -net mgt_clk_main_L1_inv1_Y
connect mgt_clk_main_L1_inv2/Y -net mgt_clk_main_L1_inv2_Y

# mgt_clk_main_L1_inv3  lower-left (5689.44, 8044.462) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_L1_inv3
place_inst mgt_clk_main_L1_inv3 5689.44 8044.462 MX
set_db inst:mgt_clk_main_L1_inv3 .place_status fixed
connect mgt_clk_main_L1_inv3/A -net mgt_clk_main_L1_inv2_Y
connect mgt_clk_main_L1_inv3/Y -net mgt_clk_main_L1_inv3_Y

# mgt_clk_main_mirror_L1_inv1  lower-left (5695.32, 5620.794) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_mirror_L1_inv1
place_inst mgt_clk_main_mirror_L1_inv1 5695.32 5620.794 MX
set_db inst:mgt_clk_main_mirror_L1_inv1 .place_status fixed
connect mgt_clk_main_mirror_L1_inv1/A -net mgt_clk_main_primary_input
connect mgt_clk_main_mirror_L1_inv1/Y -net mgt_clk_main_mirror_L1_inv1_Y

# mgt_clk_main_mirror_L1_inv2  lower-left (5695.32, 4421.152) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_mirror_L1_inv2
place_inst mgt_clk_main_mirror_L1_inv2 5695.32 4421.152 R0
set_db inst:mgt_clk_main_mirror_L1_inv2 .place_status fixed
connect mgt_clk_main_mirror_L1_inv2/A -net mgt_clk_main_mirror_L1_inv1_Y
connect mgt_clk_main_mirror_L1_inv2/Y -net mgt_clk_main_mirror_L1_inv2_Y

# mgt_clk_main_mirror_L1_inv3  lower-left (5605.08, 3313.204) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_mirror_L1_inv3
place_inst mgt_clk_main_mirror_L1_inv3 5605.08 3313.204 R0
set_db inst:mgt_clk_main_mirror_L1_inv3 .place_status fixed
connect mgt_clk_main_mirror_L1_inv3/A -net mgt_clk_main_mirror_L1_inv2_Y
connect mgt_clk_main_mirror_L1_inv3/Y -net mgt_clk_main_mirror_L1_inv3_Y

# ============================================================
# Step 3: Place and connect spine mgt_clk_main level L2
# ============================================================

# mgt_clk_main_L2_inv1  lower-left (5686.32, 8037.35) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_L2_inv1
place_inst mgt_clk_main_L2_inv1 5686.32 8037.35 MX
set_db inst:mgt_clk_main_L2_inv1 .place_status fixed
connect mgt_clk_main_L2_inv1/A -net mgt_clk_main_L1_inv2_Y
connect mgt_clk_main_L2_inv1/Y -net mgt_clk_main_L2_inv1_Y

# mgt_clk_main_mirror_L2_inv1  lower-left (5600.28, 3306.092) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_mirror_L2_inv1
place_inst mgt_clk_main_mirror_L2_inv1 5600.28 3306.092 R0
set_db inst:mgt_clk_main_mirror_L2_inv1 .place_status fixed
connect mgt_clk_main_mirror_L2_inv1/A -net mgt_clk_main_mirror_L1_inv2_Y
connect mgt_clk_main_mirror_L2_inv1/Y -net mgt_clk_main_mirror_L2_inv1_Y

# ============================================================
# Step 4: Place and connect spine mgt_clk_main level L3
# ============================================================

# mgt_clk_main_L3_inv1  lower-left (5686.68, 9240.802) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_L3_inv1
place_inst mgt_clk_main_L3_inv1 5686.68 9240.802 MX
set_db inst:mgt_clk_main_L3_inv1 .place_status fixed
connect mgt_clk_main_L3_inv1/A -net mgt_clk_main_L1_inv3_Y
connect mgt_clk_main_L3_inv1/Y -net mgt_clk_main_L3_inv1_Y

# mgt_clk_main_L3_inv2  lower-left (5686.68, 6841.264) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_L3_inv2
place_inst mgt_clk_main_L3_inv2 5686.68 6841.264 R0
set_db inst:mgt_clk_main_L3_inv2 .place_status fixed
connect mgt_clk_main_L3_inv2/A -net mgt_clk_main_L2_inv1_Y
connect mgt_clk_main_L3_inv2/Y -net mgt_clk_main_L3_inv2_Y

# mgt_clk_main_mirror_L3_inv1  lower-left (5597.4, 2108.736) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_mirror_L3_inv1
place_inst mgt_clk_main_mirror_L3_inv1 5597.4 2108.736 R0
set_db inst:mgt_clk_main_mirror_L3_inv1 .place_status fixed
connect mgt_clk_main_mirror_L3_inv1/A -net mgt_clk_main_mirror_L1_inv3_Y
connect mgt_clk_main_mirror_L3_inv1/Y -net mgt_clk_main_mirror_L3_inv1_Y

# mgt_clk_main_mirror_L3_inv2  lower-left (5686.68, 4420.898) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_mirror_L3_inv2
place_inst mgt_clk_main_mirror_L3_inv2 5686.68 4420.898 MX
set_db inst:mgt_clk_main_mirror_L3_inv2 .place_status fixed
connect mgt_clk_main_mirror_L3_inv2/A -net mgt_clk_main_mirror_L2_inv1_Y
connect mgt_clk_main_mirror_L3_inv2/Y -net mgt_clk_main_mirror_L3_inv2_Y

# ============================================================
# Step 5: Place and connect spine mgt_clk_main level L4
# ============================================================

# mgt_clk_main_L4_inv1  lower-left (5683.8, 9841.258) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_L4_inv1
place_inst mgt_clk_main_L4_inv1 5683.8 9841.258 MX
set_db inst:mgt_clk_main_L4_inv1 .place_status fixed
connect mgt_clk_main_L4_inv1/A -net mgt_clk_main_L3_inv1_Y
connect mgt_clk_main_L4_inv1/Y -net mgt_clk_main_L4_inv1_Y

# mgt_clk_main_L4_inv2  lower-left (5683.8, 8641.108) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_L4_inv2
place_inst mgt_clk_main_L4_inv2 5683.8 8641.108 R0
set_db inst:mgt_clk_main_L4_inv2 .place_status fixed
connect mgt_clk_main_L4_inv2/A -net mgt_clk_main_L3_inv1_Y
connect mgt_clk_main_L4_inv2/Y -net mgt_clk_main_L4_inv2_Y

# mgt_clk_main_L4_inv3  lower-left (5683.8, 7440.958) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_L4_inv3
place_inst mgt_clk_main_L4_inv3 5683.8 7440.958 MX
set_db inst:mgt_clk_main_L4_inv3 .place_status fixed
connect mgt_clk_main_L4_inv3/A -net mgt_clk_main_L3_inv2_Y
connect mgt_clk_main_L4_inv3/Y -net mgt_clk_main_L4_inv3_Y

# mgt_clk_main_L4_inv4  lower-left (5683.8, 6240.808) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_L4_inv4
place_inst mgt_clk_main_L4_inv4 5683.8 6240.808 R0
set_db inst:mgt_clk_main_L4_inv4 .place_status fixed
connect mgt_clk_main_L4_inv4/A -net mgt_clk_main_L3_inv2_Y
connect mgt_clk_main_L4_inv4/Y -net mgt_clk_main_L4_inv4_Y

# mgt_clk_main_mirror_L4_inv1  lower-left (5594.52, 1508.788) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_mirror_L4_inv1
place_inst mgt_clk_main_mirror_L4_inv1 5594.52 1508.788 R0
set_db inst:mgt_clk_main_mirror_L4_inv1 .place_status fixed
connect mgt_clk_main_mirror_L4_inv1/A -net mgt_clk_main_mirror_L3_inv1_Y
connect mgt_clk_main_mirror_L4_inv1/Y -net mgt_clk_main_mirror_L4_inv1_Y

# mgt_clk_main_mirror_L4_inv2  lower-left (5594.52, 2708.938) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_mirror_L4_inv2
place_inst mgt_clk_main_mirror_L4_inv2 5594.52 2708.938 MX
set_db inst:mgt_clk_main_mirror_L4_inv2 .place_status fixed
connect mgt_clk_main_mirror_L4_inv2/A -net mgt_clk_main_mirror_L3_inv1_Y
connect mgt_clk_main_mirror_L4_inv2/Y -net mgt_clk_main_mirror_L4_inv2_Y

# mgt_clk_main_mirror_L4_inv3  lower-left (5683.8, 3821.204) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_mirror_L4_inv3
place_inst mgt_clk_main_mirror_L4_inv3 5683.8 3821.204 R0
set_db inst:mgt_clk_main_mirror_L4_inv3 .place_status fixed
connect mgt_clk_main_mirror_L4_inv3/A -net mgt_clk_main_mirror_L3_inv2_Y
connect mgt_clk_main_mirror_L4_inv3/Y -net mgt_clk_main_mirror_L4_inv3_Y

# mgt_clk_main_mirror_L4_inv4  lower-left (5683.8, 5020.846) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_mirror_L4_inv4
place_inst mgt_clk_main_mirror_L4_inv4 5683.8 5020.846 MX
set_db inst:mgt_clk_main_mirror_L4_inv4 .place_status fixed
connect mgt_clk_main_mirror_L4_inv4/A -net mgt_clk_main_mirror_L3_inv2_Y
connect mgt_clk_main_mirror_L4_inv4/Y -net mgt_clk_main_mirror_L4_inv4_Y

# ============================================================
# Step 6: Place and connect spine mgt_clk_clk_spine_bot level L1
# ============================================================

# mgt_clk_clk_spine_bot_L1_inv1  lower-left (5585.88, 2986.052) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_bot_L1_inv1
place_inst mgt_clk_clk_spine_bot_L1_inv1 5585.88 2986.052 R0
set_db inst:mgt_clk_clk_spine_bot_L1_inv1 .place_status fixed
connect mgt_clk_clk_spine_bot_L1_inv1/A -net mgt_clk_clk_spine_bot_primary_input
connect mgt_clk_clk_spine_bot_L1_inv1/Y -net mgt_clk_clk_spine_bot_L1_inv1_Y

# mgt_clk_clk_spine_bot_mirror_L1_inv1  lower-left (5585.88, 2965.986) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_bot_mirror_L1_inv1
place_inst mgt_clk_clk_spine_bot_mirror_L1_inv1 5585.88 2965.986 MX
set_db inst:mgt_clk_clk_spine_bot_mirror_L1_inv1 .place_status fixed
connect mgt_clk_clk_spine_bot_mirror_L1_inv1/A -net mgt_clk_clk_spine_bot_primary_input
connect mgt_clk_clk_spine_bot_mirror_L1_inv1/Y -net mgt_clk_clk_spine_bot_mirror_L1_inv1_Y

# ============================================================
# Step 7: Place and connect spine mgt_clk_clk_spine_bot level L2
# ============================================================

# mgt_clk_clk_spine_bot_L2_inv1  lower-left (5675.16, 4193.822) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_bot_L2_inv1
place_inst mgt_clk_clk_spine_bot_L2_inv1 5675.16 4193.822 MX
set_db inst:mgt_clk_clk_spine_bot_L2_inv1 .place_status fixed
connect mgt_clk_clk_spine_bot_L2_inv1/A -net mgt_clk_clk_spine_bot_L1_inv1_Y
connect mgt_clk_clk_spine_bot_L2_inv1/Y -net mgt_clk_clk_spine_bot_L2_inv1_Y

# mgt_clk_clk_spine_bot_mirror_L2_inv1  lower-left (5583, 1666.268) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_bot_mirror_L2_inv1
place_inst mgt_clk_clk_spine_bot_mirror_L2_inv1 5583 1666.268 R0
set_db inst:mgt_clk_clk_spine_bot_mirror_L2_inv1 .place_status fixed
connect mgt_clk_clk_spine_bot_mirror_L2_inv1/A -net mgt_clk_clk_spine_bot_mirror_L1_inv1_Y
connect mgt_clk_clk_spine_bot_mirror_L2_inv1/Y -net mgt_clk_clk_spine_bot_mirror_L2_inv1_Y

# ============================================================
# Step 8: Place and connect spine mgt_clk_clk_spine_bot level L3
# ============================================================

# mgt_clk_clk_spine_bot_L3_inv1  lower-left (5672.28, 4844.062) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_bot_L3_inv1
place_inst mgt_clk_clk_spine_bot_L3_inv1 5672.28 4844.062 MX
set_db inst:mgt_clk_clk_spine_bot_L3_inv1 .place_status fixed
connect mgt_clk_clk_spine_bot_L3_inv1/A -net mgt_clk_clk_spine_bot_L2_inv1_Y
connect mgt_clk_clk_spine_bot_L3_inv1/Y -net mgt_clk_clk_spine_bot_L3_inv1_Y

# mgt_clk_clk_spine_bot_L3_inv2  lower-left (5672.28, 3543.836) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_bot_L3_inv2
place_inst mgt_clk_clk_spine_bot_L3_inv2 5672.28 3543.836 R0
set_db inst:mgt_clk_clk_spine_bot_L3_inv2 .place_status fixed
connect mgt_clk_clk_spine_bot_L3_inv2/A -net mgt_clk_clk_spine_bot_L2_inv1_Y
connect mgt_clk_clk_spine_bot_L3_inv2/Y -net mgt_clk_clk_spine_bot_L3_inv2_Y

# mgt_clk_clk_spine_bot_mirror_L3_inv1  lower-left (5580.12, 1016.028) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_bot_mirror_L3_inv1
place_inst mgt_clk_clk_spine_bot_mirror_L3_inv1 5580.12 1016.028 R0
set_db inst:mgt_clk_clk_spine_bot_mirror_L3_inv1 .place_status fixed
connect mgt_clk_clk_spine_bot_mirror_L3_inv1/A -net mgt_clk_clk_spine_bot_mirror_L2_inv1_Y
connect mgt_clk_clk_spine_bot_mirror_L3_inv1/Y -net mgt_clk_clk_spine_bot_mirror_L3_inv1_Y

# mgt_clk_clk_spine_bot_mirror_L3_inv2  lower-left (5580.12, 2316.254) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_bot_mirror_L3_inv2
place_inst mgt_clk_clk_spine_bot_mirror_L3_inv2 5580.12 2316.254 MX
set_db inst:mgt_clk_clk_spine_bot_mirror_L3_inv2 .place_status fixed
connect mgt_clk_clk_spine_bot_mirror_L3_inv2/A -net mgt_clk_clk_spine_bot_mirror_L2_inv1_Y
connect mgt_clk_clk_spine_bot_mirror_L3_inv2/Y -net mgt_clk_clk_spine_bot_mirror_L3_inv2_Y

# ============================================================
# Step 9: Place and connect spine mgt_clk_clk_spine_top level L1
# ============================================================

# mgt_clk_clk_spine_top_L1_inv1  lower-left (5678.04, 11054.108) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_top_L1_inv1
place_inst mgt_clk_clk_spine_top_L1_inv1 5678.04 11054.108 R0
set_db inst:mgt_clk_clk_spine_top_L1_inv1 .place_status fixed
connect mgt_clk_clk_spine_top_L1_inv1/A -net mgt_clk_clk_spine_top_primary_input
connect mgt_clk_clk_spine_top_L1_inv1/Y -net mgt_clk_clk_spine_top_L1_inv1_Y

# mgt_clk_clk_spine_top_mirror_L1_inv1  lower-left (5678.04, 11034.042) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_top_mirror_L1_inv1
place_inst mgt_clk_clk_spine_top_mirror_L1_inv1 5678.04 11034.042 MX
set_db inst:mgt_clk_clk_spine_top_mirror_L1_inv1 .place_status fixed
connect mgt_clk_clk_spine_top_mirror_L1_inv1/A -net mgt_clk_clk_spine_top_primary_input
connect mgt_clk_clk_spine_top_mirror_L1_inv1/Y -net mgt_clk_clk_spine_top_mirror_L1_inv1_Y

# ============================================================
# Step 10: Place and connect spine mgt_clk_clk_spine_top level L2
# ============================================================

# mgt_clk_clk_spine_top_L2_inv1  lower-left (5675.16, 12354.334) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_top_L2_inv1
place_inst mgt_clk_clk_spine_top_L2_inv1 5675.16 12354.334 MX
set_db inst:mgt_clk_clk_spine_top_L2_inv1 .place_status fixed
connect mgt_clk_clk_spine_top_L2_inv1/A -net mgt_clk_clk_spine_top_L1_inv1_Y
connect mgt_clk_clk_spine_top_L2_inv1/Y -net mgt_clk_clk_spine_top_L2_inv1_Y

# mgt_clk_clk_spine_top_mirror_L2_inv1  lower-left (5675.16, 9734.324) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_top_mirror_L2_inv1
place_inst mgt_clk_clk_spine_top_mirror_L2_inv1 5675.16 9734.324 R0
set_db inst:mgt_clk_clk_spine_top_mirror_L2_inv1 .place_status fixed
connect mgt_clk_clk_spine_top_mirror_L2_inv1/A -net mgt_clk_clk_spine_top_mirror_L1_inv1_Y
connect mgt_clk_clk_spine_top_mirror_L2_inv1/Y -net mgt_clk_clk_spine_top_mirror_L2_inv1_Y

# ============================================================
# Step 11: Place and connect spine mgt_clk_clk_spine_top level L3
# ============================================================

# mgt_clk_clk_spine_top_L3_inv1  lower-left (5672.28, 13004.066) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_top_L3_inv1
place_inst mgt_clk_clk_spine_top_L3_inv1 5672.28 13004.066 MX
set_db inst:mgt_clk_clk_spine_top_L3_inv1 .place_status fixed
connect mgt_clk_clk_spine_top_L3_inv1/A -net mgt_clk_clk_spine_top_L2_inv1_Y
connect mgt_clk_clk_spine_top_L3_inv1/Y -net mgt_clk_clk_spine_top_L3_inv1_Y

# mgt_clk_clk_spine_top_L3_inv2  lower-left (5672.28, 11704.348) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_top_L3_inv2
place_inst mgt_clk_clk_spine_top_L3_inv2 5672.28 11704.348 R0
set_db inst:mgt_clk_clk_spine_top_L3_inv2 .place_status fixed
connect mgt_clk_clk_spine_top_L3_inv2/A -net mgt_clk_clk_spine_top_L2_inv1_Y
connect mgt_clk_clk_spine_top_L3_inv2/Y -net mgt_clk_clk_spine_top_L3_inv2_Y

# mgt_clk_clk_spine_top_mirror_L3_inv1  lower-left (5672.28, 9084.084) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_top_mirror_L3_inv1
place_inst mgt_clk_clk_spine_top_mirror_L3_inv1 5672.28 9084.084 R0
set_db inst:mgt_clk_clk_spine_top_mirror_L3_inv1 .place_status fixed
connect mgt_clk_clk_spine_top_mirror_L3_inv1/A -net mgt_clk_clk_spine_top_mirror_L2_inv1_Y
connect mgt_clk_clk_spine_top_mirror_L3_inv1/Y -net mgt_clk_clk_spine_top_mirror_L3_inv1_Y

# mgt_clk_clk_spine_top_mirror_L3_inv2  lower-left (5672.28, 10384.31) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_top_mirror_L3_inv2
place_inst mgt_clk_clk_spine_top_mirror_L3_inv2 5672.28 10384.31 MX
set_db inst:mgt_clk_clk_spine_top_mirror_L3_inv2 .place_status fixed
connect mgt_clk_clk_spine_top_mirror_L3_inv2/A -net mgt_clk_clk_spine_top_mirror_L2_inv1_Y
connect mgt_clk_clk_spine_top_mirror_L3_inv2/Y -net mgt_clk_clk_spine_top_mirror_L3_inv2_Y

# ============================================================
# Step 12: Place and connect spine soc_clk_main level L1
# ============================================================

# soc_clk_main_L1_inv1  lower-left (5660.76, 5675.404) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_L1_inv1
place_inst soc_clk_main_L1_inv1 5660.76 5675.404 R0
set_db inst:soc_clk_main_L1_inv1 .place_status fixed
connect soc_clk_main_L1_inv1/A -net soc_clk_main_primary_input
connect soc_clk_main_L1_inv1/Y -net soc_clk_main_L1_inv1_Y

# soc_clk_main_L1_inv2  lower-left (5660.76, 6875.554) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_L1_inv2
place_inst soc_clk_main_L1_inv2 5660.76 6875.554 MX
set_db inst:soc_clk_main_L1_inv2 .place_status fixed
connect soc_clk_main_L1_inv2/A -net soc_clk_main_L1_inv1_Y
connect soc_clk_main_L1_inv2/Y -net soc_clk_main_L1_inv2_Y

# soc_clk_main_L1_inv3  lower-left (5654.88, 8079.006) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_L1_inv3
place_inst soc_clk_main_L1_inv3 5654.88 8079.006 MX
set_db inst:soc_clk_main_L1_inv3 .place_status fixed
connect soc_clk_main_L1_inv3/A -net soc_clk_main_L1_inv2_Y
connect soc_clk_main_L1_inv3/Y -net soc_clk_main_L1_inv3_Y

# soc_clk_main_mirror_L1_inv1  lower-left (5660.76, 5655.338) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_mirror_L1_inv1
place_inst soc_clk_main_mirror_L1_inv1 5660.76 5655.338 MX
set_db inst:soc_clk_main_mirror_L1_inv1 .place_status fixed
connect soc_clk_main_mirror_L1_inv1/A -net soc_clk_main_primary_input
connect soc_clk_main_mirror_L1_inv1/Y -net soc_clk_main_mirror_L1_inv1_Y

# soc_clk_main_mirror_L1_inv2  lower-left (5660.76, 4455.696) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_mirror_L1_inv2
place_inst soc_clk_main_mirror_L1_inv2 5660.76 4455.696 R0
set_db inst:soc_clk_main_mirror_L1_inv2 .place_status fixed
connect soc_clk_main_mirror_L1_inv2/A -net soc_clk_main_mirror_L1_inv1_Y
connect soc_clk_main_mirror_L1_inv2/Y -net soc_clk_main_mirror_L1_inv2_Y

# soc_clk_main_mirror_L1_inv3  lower-left (5570.52, 3347.748) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_mirror_L1_inv3
place_inst soc_clk_main_mirror_L1_inv3 5570.52 3347.748 R0
set_db inst:soc_clk_main_mirror_L1_inv3 .place_status fixed
connect soc_clk_main_mirror_L1_inv3/A -net soc_clk_main_mirror_L1_inv2_Y
connect soc_clk_main_mirror_L1_inv3/Y -net soc_clk_main_mirror_L1_inv3_Y

# ============================================================
# Step 13: Place and connect spine soc_clk_main level L2
# ============================================================

# soc_clk_main_L2_inv1  lower-left (5651.76, 8071.894) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_L2_inv1
place_inst soc_clk_main_L2_inv1 5651.76 8071.894 MX
set_db inst:soc_clk_main_L2_inv1 .place_status fixed
connect soc_clk_main_L2_inv1/A -net soc_clk_main_L1_inv2_Y
connect soc_clk_main_L2_inv1/Y -net soc_clk_main_L2_inv1_Y

# soc_clk_main_mirror_L2_inv1  lower-left (5565.72, 3340.636) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_mirror_L2_inv1
place_inst soc_clk_main_mirror_L2_inv1 5565.72 3340.636 R0
set_db inst:soc_clk_main_mirror_L2_inv1 .place_status fixed
connect soc_clk_main_mirror_L2_inv1/A -net soc_clk_main_mirror_L1_inv2_Y
connect soc_clk_main_mirror_L2_inv1/Y -net soc_clk_main_mirror_L2_inv1_Y

# ============================================================
# Step 14: Place and connect spine soc_clk_main level L3
# ============================================================

# soc_clk_main_L3_inv1  lower-left (5652.12, 9275.346) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_L3_inv1
place_inst soc_clk_main_L3_inv1 5652.12 9275.346 MX
set_db inst:soc_clk_main_L3_inv1 .place_status fixed
connect soc_clk_main_L3_inv1/A -net soc_clk_main_L1_inv3_Y
connect soc_clk_main_L3_inv1/Y -net soc_clk_main_L3_inv1_Y

# soc_clk_main_L3_inv2  lower-left (5652.12, 6875.808) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_L3_inv2
place_inst soc_clk_main_L3_inv2 5652.12 6875.808 R0
set_db inst:soc_clk_main_L3_inv2 .place_status fixed
connect soc_clk_main_L3_inv2/A -net soc_clk_main_L2_inv1_Y
connect soc_clk_main_L3_inv2/Y -net soc_clk_main_L3_inv2_Y

# soc_clk_main_mirror_L3_inv1  lower-left (5562.84, 2143.28) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_mirror_L3_inv1
place_inst soc_clk_main_mirror_L3_inv1 5562.84 2143.28 R0
set_db inst:soc_clk_main_mirror_L3_inv1 .place_status fixed
connect soc_clk_main_mirror_L3_inv1/A -net soc_clk_main_mirror_L1_inv3_Y
connect soc_clk_main_mirror_L3_inv1/Y -net soc_clk_main_mirror_L3_inv1_Y

# soc_clk_main_mirror_L3_inv2  lower-left (5652.12, 4455.442) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_mirror_L3_inv2
place_inst soc_clk_main_mirror_L3_inv2 5652.12 4455.442 MX
set_db inst:soc_clk_main_mirror_L3_inv2 .place_status fixed
connect soc_clk_main_mirror_L3_inv2/A -net soc_clk_main_mirror_L2_inv1_Y
connect soc_clk_main_mirror_L3_inv2/Y -net soc_clk_main_mirror_L3_inv2_Y

# ============================================================
# Step 15: Place and connect spine soc_clk_main level L4
# ============================================================

# soc_clk_main_L4_inv1  lower-left (5649.24, 9875.802) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_L4_inv1
place_inst soc_clk_main_L4_inv1 5649.24 9875.802 MX
set_db inst:soc_clk_main_L4_inv1 .place_status fixed
connect soc_clk_main_L4_inv1/A -net soc_clk_main_L3_inv1_Y
connect soc_clk_main_L4_inv1/Y -net soc_clk_main_L4_inv1_Y

# soc_clk_main_L4_inv2  lower-left (5649.24, 8675.652) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_L4_inv2
place_inst soc_clk_main_L4_inv2 5649.24 8675.652 R0
set_db inst:soc_clk_main_L4_inv2 .place_status fixed
connect soc_clk_main_L4_inv2/A -net soc_clk_main_L3_inv1_Y
connect soc_clk_main_L4_inv2/Y -net soc_clk_main_L4_inv2_Y

# soc_clk_main_L4_inv3  lower-left (5649.24, 7475.502) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_L4_inv3
place_inst soc_clk_main_L4_inv3 5649.24 7475.502 MX
set_db inst:soc_clk_main_L4_inv3 .place_status fixed
connect soc_clk_main_L4_inv3/A -net soc_clk_main_L3_inv2_Y
connect soc_clk_main_L4_inv3/Y -net soc_clk_main_L4_inv3_Y

# soc_clk_main_L4_inv4  lower-left (5649.24, 6275.352) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_L4_inv4
place_inst soc_clk_main_L4_inv4 5649.24 6275.352 R0
set_db inst:soc_clk_main_L4_inv4 .place_status fixed
connect soc_clk_main_L4_inv4/A -net soc_clk_main_L3_inv2_Y
connect soc_clk_main_L4_inv4/Y -net soc_clk_main_L4_inv4_Y

# soc_clk_main_mirror_L4_inv1  lower-left (5559.96, 1543.332) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_mirror_L4_inv1
place_inst soc_clk_main_mirror_L4_inv1 5559.96 1543.332 R0
set_db inst:soc_clk_main_mirror_L4_inv1 .place_status fixed
connect soc_clk_main_mirror_L4_inv1/A -net soc_clk_main_mirror_L3_inv1_Y
connect soc_clk_main_mirror_L4_inv1/Y -net soc_clk_main_mirror_L4_inv1_Y

# soc_clk_main_mirror_L4_inv2  lower-left (5559.96, 2743.482) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_mirror_L4_inv2
place_inst soc_clk_main_mirror_L4_inv2 5559.96 2743.482 MX
set_db inst:soc_clk_main_mirror_L4_inv2 .place_status fixed
connect soc_clk_main_mirror_L4_inv2/A -net soc_clk_main_mirror_L3_inv1_Y
connect soc_clk_main_mirror_L4_inv2/Y -net soc_clk_main_mirror_L4_inv2_Y

# soc_clk_main_mirror_L4_inv3  lower-left (5649.24, 3855.748) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_mirror_L4_inv3
place_inst soc_clk_main_mirror_L4_inv3 5649.24 3855.748 R0
set_db inst:soc_clk_main_mirror_L4_inv3 .place_status fixed
connect soc_clk_main_mirror_L4_inv3/A -net soc_clk_main_mirror_L3_inv2_Y
connect soc_clk_main_mirror_L4_inv3/Y -net soc_clk_main_mirror_L4_inv3_Y

# soc_clk_main_mirror_L4_inv4  lower-left (5649.24, 5055.39) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_main_mirror_L4_inv4
place_inst soc_clk_main_mirror_L4_inv4 5649.24 5055.39 MX
set_db inst:soc_clk_main_mirror_L4_inv4 .place_status fixed
connect soc_clk_main_mirror_L4_inv4/A -net soc_clk_main_mirror_L3_inv2_Y
connect soc_clk_main_mirror_L4_inv4/Y -net soc_clk_main_mirror_L4_inv4_Y

# ============================================================
# Step 16: Place and connect spine soc_clk_bot level L1
# ============================================================

# soc_clk_bot_L1_inv1  lower-left (5551.32, 3020.596) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_bot_L1_inv1
place_inst soc_clk_bot_L1_inv1 5551.32 3020.596 R0
set_db inst:soc_clk_bot_L1_inv1 .place_status fixed
connect soc_clk_bot_L1_inv1/A -net soc_clk_bot_primary_input
connect soc_clk_bot_L1_inv1/Y -net soc_clk_bot_L1_inv1_Y

# soc_clk_bot_mirror_L1_inv1  lower-left (5551.32, 3000.53) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_bot_mirror_L1_inv1
place_inst soc_clk_bot_mirror_L1_inv1 5551.32 3000.53 MX
set_db inst:soc_clk_bot_mirror_L1_inv1 .place_status fixed
connect soc_clk_bot_mirror_L1_inv1/A -net soc_clk_bot_primary_input
connect soc_clk_bot_mirror_L1_inv1/Y -net soc_clk_bot_mirror_L1_inv1_Y

# ============================================================
# Step 17: Place and connect spine soc_clk_bot level L2
# ============================================================

# soc_clk_bot_L2_inv1  lower-left (5640.6, 4228.366) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_bot_L2_inv1
place_inst soc_clk_bot_L2_inv1 5640.6 4228.366 MX
set_db inst:soc_clk_bot_L2_inv1 .place_status fixed
connect soc_clk_bot_L2_inv1/A -net soc_clk_bot_L1_inv1_Y
connect soc_clk_bot_L2_inv1/Y -net soc_clk_bot_L2_inv1_Y

# soc_clk_bot_mirror_L2_inv1  lower-left (5548.44, 1700.812) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_bot_mirror_L2_inv1
place_inst soc_clk_bot_mirror_L2_inv1 5548.44 1700.812 R0
set_db inst:soc_clk_bot_mirror_L2_inv1 .place_status fixed
connect soc_clk_bot_mirror_L2_inv1/A -net soc_clk_bot_mirror_L1_inv1_Y
connect soc_clk_bot_mirror_L2_inv1/Y -net soc_clk_bot_mirror_L2_inv1_Y

# ============================================================
# Step 18: Place and connect spine soc_clk_bot level L3
# ============================================================

# soc_clk_bot_L3_inv1  lower-left (5637.72, 4878.606) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_bot_L3_inv1
place_inst soc_clk_bot_L3_inv1 5637.72 4878.606 MX
set_db inst:soc_clk_bot_L3_inv1 .place_status fixed
connect soc_clk_bot_L3_inv1/A -net soc_clk_bot_L2_inv1_Y
connect soc_clk_bot_L3_inv1/Y -net soc_clk_bot_L3_inv1_Y

# soc_clk_bot_L3_inv2  lower-left (5637.72, 3578.38) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_bot_L3_inv2
place_inst soc_clk_bot_L3_inv2 5637.72 3578.38 R0
set_db inst:soc_clk_bot_L3_inv2 .place_status fixed
connect soc_clk_bot_L3_inv2/A -net soc_clk_bot_L2_inv1_Y
connect soc_clk_bot_L3_inv2/Y -net soc_clk_bot_L3_inv2_Y

# soc_clk_bot_mirror_L3_inv1  lower-left (5545.56, 1050.572) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_bot_mirror_L3_inv1
place_inst soc_clk_bot_mirror_L3_inv1 5545.56 1050.572 R0
set_db inst:soc_clk_bot_mirror_L3_inv1 .place_status fixed
connect soc_clk_bot_mirror_L3_inv1/A -net soc_clk_bot_mirror_L2_inv1_Y
connect soc_clk_bot_mirror_L3_inv1/Y -net soc_clk_bot_mirror_L3_inv1_Y

# soc_clk_bot_mirror_L3_inv2  lower-left (5545.56, 2350.798) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_bot_mirror_L3_inv2
place_inst soc_clk_bot_mirror_L3_inv2 5545.56 2350.798 MX
set_db inst:soc_clk_bot_mirror_L3_inv2 .place_status fixed
connect soc_clk_bot_mirror_L3_inv2/A -net soc_clk_bot_mirror_L2_inv1_Y
connect soc_clk_bot_mirror_L3_inv2/Y -net soc_clk_bot_mirror_L3_inv2_Y

# ============================================================
# Step 19: Place and connect spine soc_clk_top level L1
# ============================================================

# soc_clk_top_L1_inv1  lower-left (5643.48, 11088.652) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_L1_inv1
place_inst soc_clk_top_L1_inv1 5643.48 11088.652 R0
set_db inst:soc_clk_top_L1_inv1 .place_status fixed
connect soc_clk_top_L1_inv1/A -net soc_clk_top_primary_input
connect soc_clk_top_L1_inv1/Y -net soc_clk_top_L1_inv1_Y

# soc_clk_top_mirror_L1_inv1  lower-left (5643.48, 11068.586) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_mirror_L1_inv1
place_inst soc_clk_top_mirror_L1_inv1 5643.48 11068.586 MX
set_db inst:soc_clk_top_mirror_L1_inv1 .place_status fixed
connect soc_clk_top_mirror_L1_inv1/A -net soc_clk_top_primary_input
connect soc_clk_top_mirror_L1_inv1/Y -net soc_clk_top_mirror_L1_inv1_Y

# ============================================================
# Step 20: Place and connect spine soc_clk_top level L2
# ============================================================

# soc_clk_top_L2_inv1  lower-left (5640.6, 12388.878) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_L2_inv1
place_inst soc_clk_top_L2_inv1 5640.6 12388.878 MX
set_db inst:soc_clk_top_L2_inv1 .place_status fixed
connect soc_clk_top_L2_inv1/A -net soc_clk_top_L1_inv1_Y
connect soc_clk_top_L2_inv1/Y -net soc_clk_top_L2_inv1_Y

# soc_clk_top_mirror_L2_inv1  lower-left (5640.6, 9768.868) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_mirror_L2_inv1
place_inst soc_clk_top_mirror_L2_inv1 5640.6 9768.868 R0
set_db inst:soc_clk_top_mirror_L2_inv1 .place_status fixed
connect soc_clk_top_mirror_L2_inv1/A -net soc_clk_top_mirror_L1_inv1_Y
connect soc_clk_top_mirror_L2_inv1/Y -net soc_clk_top_mirror_L2_inv1_Y

# ============================================================
# Step 21: Place and connect spine soc_clk_top level L3
# ============================================================

# soc_clk_top_L3_inv1  lower-left (5637.72, 13038.61) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_L3_inv1
place_inst soc_clk_top_L3_inv1 5637.72 13038.61 MX
set_db inst:soc_clk_top_L3_inv1 .place_status fixed
connect soc_clk_top_L3_inv1/A -net soc_clk_top_L2_inv1_Y
connect soc_clk_top_L3_inv1/Y -net soc_clk_top_L3_inv1_Y

# soc_clk_top_L3_inv2  lower-left (5637.72, 11738.892) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_L3_inv2
place_inst soc_clk_top_L3_inv2 5637.72 11738.892 R0
set_db inst:soc_clk_top_L3_inv2 .place_status fixed
connect soc_clk_top_L3_inv2/A -net soc_clk_top_L2_inv1_Y
connect soc_clk_top_L3_inv2/Y -net soc_clk_top_L3_inv2_Y

# soc_clk_top_mirror_L3_inv1  lower-left (5637.72, 9118.628) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_mirror_L3_inv1
place_inst soc_clk_top_mirror_L3_inv1 5637.72 9118.628 R0
set_db inst:soc_clk_top_mirror_L3_inv1 .place_status fixed
connect soc_clk_top_mirror_L3_inv1/A -net soc_clk_top_mirror_L2_inv1_Y
connect soc_clk_top_mirror_L3_inv1/Y -net soc_clk_top_mirror_L3_inv1_Y

# soc_clk_top_mirror_L3_inv2  lower-left (5637.72, 10418.854) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_mirror_L3_inv2
place_inst soc_clk_top_mirror_L3_inv2 5637.72 10418.854 MX
set_db inst:soc_clk_top_mirror_L3_inv2 .place_status fixed
connect soc_clk_top_mirror_L3_inv2/A -net soc_clk_top_mirror_L2_inv1_Y
connect soc_clk_top_mirror_L3_inv2/Y -net soc_clk_top_mirror_L3_inv2_Y

set_db timing_enable_simultaneous_setup_hold_mode true
