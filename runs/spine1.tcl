set_db timing_enable_simultaneous_setup_hold_mode false
# htree4 logical changes: Innovus script, source it to reproduce them.

# ============================================================
# Step 1: Create all nets
# ============================================================

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

create_net -name mgt_clk_clk_spine_bot_L1_inv1_Y
create_net -name mgt_clk_clk_spine_bot_L2_inv1_Y
create_net -name mgt_clk_clk_spine_bot_L3_inv1_Y
create_net -name mgt_clk_clk_spine_bot_L3_inv2_Y
create_net -name mgt_clk_clk_spine_bot_mirror_L1_inv1_Y
create_net -name mgt_clk_clk_spine_bot_mirror_L2_inv1_Y
create_net -name mgt_clk_clk_spine_bot_mirror_L3_inv1_Y
create_net -name mgt_clk_clk_spine_bot_mirror_L3_inv2_Y

create_net -name mgt_clk_clk_spine_top_L1_inv1_Y
create_net -name mgt_clk_clk_spine_top_L2_inv1_Y
create_net -name mgt_clk_clk_spine_top_L3_inv1_Y
create_net -name mgt_clk_clk_spine_top_L3_inv2_Y
create_net -name mgt_clk_clk_spine_top_mirror_L1_inv1_Y
create_net -name mgt_clk_clk_spine_top_mirror_L2_inv1_Y
create_net -name mgt_clk_clk_spine_top_mirror_L3_inv1_Y
create_net -name mgt_clk_clk_spine_top_mirror_L3_inv2_Y

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

create_net -name soc_clk_bot_L1_inv1_Y
create_net -name soc_clk_bot_L2_inv1_Y
create_net -name soc_clk_bot_L3_inv1_Y
create_net -name soc_clk_bot_L3_inv2_Y
create_net -name soc_clk_bot_mirror_L1_inv1_Y
create_net -name soc_clk_bot_mirror_L2_inv1_Y
create_net -name soc_clk_bot_mirror_L3_inv1_Y
create_net -name soc_clk_bot_mirror_L3_inv2_Y

create_net -name soc_clk_top_L1_inv1_Y
create_net -name soc_clk_top_L2_inv1_Y
create_net -name soc_clk_top_L3_inv1_Y
create_net -name soc_clk_top_L3_inv2_Y
create_net -name soc_clk_top_mirror_L1_inv1_Y
create_net -name soc_clk_top_mirror_L2_inv1_Y
create_net -name soc_clk_top_mirror_L3_inv1_Y
create_net -name soc_clk_top_mirror_L3_inv2_Y

create_net -name mgt_clk_hor1_L1_inv1_Y
create_net -name mgt_clk_hor1_L2_inv1_Y
create_net -name mgt_clk_hor1_L3_inv1_Y
create_net -name mgt_clk_hor1_L3_inv2_Y
create_net -name mgt_clk_hor1_mirror_L1_inv1_Y
create_net -name mgt_clk_hor1_mirror_L2_inv1_Y
create_net -name mgt_clk_hor1_mirror_L3_inv1_Y
create_net -name mgt_clk_hor1_mirror_L3_inv2_Y

create_net -name soc_clk_hor1_L1_inv1_Y
create_net -name soc_clk_hor1_L2_inv1_Y
create_net -name soc_clk_hor1_L3_inv1_Y
create_net -name soc_clk_hor1_L3_inv2_Y
create_net -name soc_clk_hor1_mirror_L1_inv1_Y
create_net -name soc_clk_hor1_mirror_L2_inv1_Y
create_net -name soc_clk_hor1_mirror_L3_inv1_Y
create_net -name soc_clk_hor1_mirror_L3_inv2_Y

create_net -name mgt_clk_hor2_L1_inv1_Y
create_net -name mgt_clk_hor2_L2_inv1_Y
create_net -name mgt_clk_hor2_L3_inv1_Y
create_net -name mgt_clk_hor2_L3_inv2_Y
create_net -name mgt_clk_hor2_mirror_L1_inv1_Y
create_net -name mgt_clk_hor2_mirror_L2_inv1_Y
create_net -name mgt_clk_hor2_mirror_L3_inv1_Y
create_net -name mgt_clk_hor2_mirror_L3_inv2_Y

create_net -name soc_clk_hor2_L1_inv1_Y
create_net -name soc_clk_hor2_L2_inv1_Y
create_net -name soc_clk_hor2_L3_inv1_Y
create_net -name soc_clk_hor2_L3_inv2_Y
create_net -name soc_clk_hor2_mirror_L1_inv1_Y
create_net -name soc_clk_hor2_mirror_L2_inv1_Y
create_net -name soc_clk_hor2_mirror_L3_inv1_Y
create_net -name soc_clk_hor2_mirror_L3_inv2_Y

create_net -name mgt_clk_hor3_L1_inv1_Y
create_net -name mgt_clk_hor3_L2_inv1_Y
create_net -name mgt_clk_hor3_L3_inv1_Y
create_net -name mgt_clk_hor3_L3_inv2_Y
create_net -name mgt_clk_hor3_mirror_L1_inv1_Y
create_net -name mgt_clk_hor3_mirror_L2_inv1_Y
create_net -name mgt_clk_hor3_mirror_L3_inv1_Y
create_net -name mgt_clk_hor3_mirror_L3_inv2_Y

create_net -name soc_clk_hor3_L1_inv1_Y
create_net -name soc_clk_hor3_L2_inv1_Y
create_net -name soc_clk_hor3_L3_inv1_Y
create_net -name soc_clk_hor3_L3_inv2_Y
create_net -name soc_clk_hor3_mirror_L1_inv1_Y
create_net -name soc_clk_hor3_mirror_L2_inv1_Y
create_net -name soc_clk_hor3_mirror_L3_inv1_Y
create_net -name soc_clk_hor3_mirror_L3_inv2_Y

create_net -name mgt_clk_hor4_L1_inv1_Y
create_net -name mgt_clk_hor4_L2_inv1_Y
create_net -name mgt_clk_hor4_L3_inv1_Y
create_net -name mgt_clk_hor4_L3_inv2_Y
create_net -name mgt_clk_hor4_mirror_L1_inv1_Y
create_net -name mgt_clk_hor4_mirror_L2_inv1_Y
create_net -name mgt_clk_hor4_mirror_L3_inv1_Y
create_net -name mgt_clk_hor4_mirror_L3_inv2_Y

create_net -name soc_clk_hor4_L1_inv1_Y
create_net -name soc_clk_hor4_L2_inv1_Y
create_net -name soc_clk_hor4_L3_inv1_Y
create_net -name soc_clk_hor4_L3_inv2_Y
create_net -name soc_clk_hor4_mirror_L1_inv1_Y
create_net -name soc_clk_hor4_mirror_L2_inv1_Y
create_net -name soc_clk_hor4_mirror_L3_inv1_Y
create_net -name soc_clk_hor4_mirror_L3_inv2_Y

create_net -name mgt_clk_hor5_L1_inv1_Y
create_net -name mgt_clk_hor5_L2_inv1_Y
create_net -name mgt_clk_hor5_L3_inv1_Y
create_net -name mgt_clk_hor5_L3_inv2_Y
create_net -name mgt_clk_hor5_mirror_L1_inv1_Y
create_net -name mgt_clk_hor5_mirror_L2_inv1_Y
create_net -name mgt_clk_hor5_mirror_L3_inv1_Y
create_net -name mgt_clk_hor5_mirror_L3_inv2_Y

create_net -name soc_clk_hor5_L1_inv1_Y
create_net -name soc_clk_hor5_L2_inv1_Y
create_net -name soc_clk_hor5_L3_inv1_Y
create_net -name soc_clk_hor5_L3_inv2_Y
create_net -name soc_clk_hor5_mirror_L1_inv1_Y
create_net -name soc_clk_hor5_mirror_L2_inv1_Y
create_net -name soc_clk_hor5_mirror_L3_inv1_Y
create_net -name soc_clk_hor5_mirror_L3_inv2_Y

# connect_pin: net mgt_clk_ione_ctm2_clk_out_31_2_clock of port mgt_clk_ione_ctm2_clk_out_31_2_clock must exist in the design
# connect_pin: net soc_clk_ione_ctm4_clk_out_31_4_clock of port soc_clk_ione_ctm4_clk_out_31_4_clock must exist in the design
create_net -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_1_Y
create_net -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_2_Y
create_net -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_3_Y
create_net -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_4_Y
create_net -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_5_Y
create_net -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_6_Y
create_net -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_7_Y
create_net -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_8_Y
create_net -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_1_Y
create_net -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_2_Y
create_net -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_3_Y
create_net -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_4_Y
create_net -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_5_Y
create_net -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_6_Y
create_net -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_7_Y
create_net -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_8_Y
create_net -name spine_connect_bot_mgt_clk_clk_spine_bot_Y
create_net -name mid_buffer_1_Y
create_net -name spine_connect_top_mgt_clk_clk_spine_top_Y
create_net -name mid_buffer_2_Y
create_net -name spine_connect_bot_soc_clk_bot_Y
create_net -name mid_buffer_3_Y
create_net -name spine_connect_top_soc_clk_top_Y
create_net -name mid_buffer_4_Y
create_net -name mgt_clk_hor1_fwd_clk_mgt_clk_hor1_Y
create_net -name mgt_clk_hor2_fwd_clk_mgt_clk_hor2_Y
create_net -name mgt_clk_hor3_fwd_clk_mgt_clk_hor3_Y
create_net -name mgt_clk_hor4_fwd_clk_mgt_clk_hor4_Y
create_net -name mgt_clk_hor5_fwd_clk_mgt_clk_hor5_Y
create_net -name soc_clk_hor1_fwd_clk_soc_clk_hor1_Y
create_net -name soc_clk_hor2_fwd_clk_soc_clk_hor2_Y
create_net -name soc_clk_hor3_fwd_clk_soc_clk_hor3_Y
create_net -name soc_clk_hor4_fwd_clk_soc_clk_hor4_Y
create_net -name soc_clk_hor5_fwd_clk_soc_clk_hor5_Y

# ============================================================
# Step 2: Place and connect spine mgt_clk_main level L1
# ============================================================

# mgt_clk_main_L1_inv1  lower-left (5695.32, 5640.86) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_main_L1_inv1
place_inst mgt_clk_main_L1_inv1 5695.32 5640.86 R0
set_db inst:mgt_clk_main_L1_inv1 .place_status fixed
connect mgt_clk_main_L1_inv1/A -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_8_Y
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
connect mgt_clk_main_mirror_L1_inv1/A -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_8_Y
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
connect mgt_clk_clk_spine_bot_L1_inv1/A -net mid_buffer_1_Y
connect mgt_clk_clk_spine_bot_L1_inv1/Y -net mgt_clk_clk_spine_bot_L1_inv1_Y

# mgt_clk_clk_spine_bot_mirror_L1_inv1  lower-left (5585.88, 2965.986) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_bot_mirror_L1_inv1
place_inst mgt_clk_clk_spine_bot_mirror_L1_inv1 5585.88 2965.986 MX
set_db inst:mgt_clk_clk_spine_bot_mirror_L1_inv1 .place_status fixed
connect mgt_clk_clk_spine_bot_mirror_L1_inv1/A -net mid_buffer_1_Y
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
connect mgt_clk_clk_spine_top_L1_inv1/A -net mid_buffer_2_Y
connect mgt_clk_clk_spine_top_L1_inv1/Y -net mgt_clk_clk_spine_top_L1_inv1_Y

# mgt_clk_clk_spine_top_mirror_L1_inv1  lower-left (5678.04, 11034.042) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_clk_spine_top_mirror_L1_inv1
place_inst mgt_clk_clk_spine_top_mirror_L1_inv1 5678.04 11034.042 MX
set_db inst:mgt_clk_clk_spine_top_mirror_L1_inv1 .place_status fixed
connect mgt_clk_clk_spine_top_mirror_L1_inv1/A -net mid_buffer_2_Y
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
connect soc_clk_main_L1_inv1/A -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_8_Y
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
connect soc_clk_main_mirror_L1_inv1/A -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_8_Y
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
connect soc_clk_bot_L1_inv1/A -net mid_buffer_3_Y
connect soc_clk_bot_L1_inv1/Y -net soc_clk_bot_L1_inv1_Y

# soc_clk_bot_mirror_L1_inv1  lower-left (5551.32, 3000.53) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_bot_mirror_L1_inv1
place_inst soc_clk_bot_mirror_L1_inv1 5551.32 3000.53 MX
set_db inst:soc_clk_bot_mirror_L1_inv1 .place_status fixed
connect soc_clk_bot_mirror_L1_inv1/A -net mid_buffer_3_Y
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

# soc_clk_top_L1_inv1  lower-left (5643.48, 11089.16) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_L1_inv1
place_inst soc_clk_top_L1_inv1 5643.48 11089.16 R0
set_db inst:soc_clk_top_L1_inv1 .place_status fixed
connect soc_clk_top_L1_inv1/A -net mid_buffer_4_Y
connect soc_clk_top_L1_inv1/Y -net soc_clk_top_L1_inv1_Y

# soc_clk_top_mirror_L1_inv1  lower-left (5643.48, 11069.094) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_mirror_L1_inv1
place_inst soc_clk_top_mirror_L1_inv1 5643.48 11069.094 MX
set_db inst:soc_clk_top_mirror_L1_inv1 .place_status fixed
connect soc_clk_top_mirror_L1_inv1/A -net mid_buffer_4_Y
connect soc_clk_top_mirror_L1_inv1/Y -net soc_clk_top_mirror_L1_inv1_Y

# ============================================================
# Step 20: Place and connect spine soc_clk_top level L2
# ============================================================

# soc_clk_top_L2_inv1  lower-left (5640.6, 12389.386) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_L2_inv1
place_inst soc_clk_top_L2_inv1 5640.6 12389.386 MX
set_db inst:soc_clk_top_L2_inv1 .place_status fixed
connect soc_clk_top_L2_inv1/A -net soc_clk_top_L1_inv1_Y
connect soc_clk_top_L2_inv1/Y -net soc_clk_top_L2_inv1_Y

# soc_clk_top_mirror_L2_inv1  lower-left (5640.6, 9769.376) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_mirror_L2_inv1
place_inst soc_clk_top_mirror_L2_inv1 5640.6 9769.376 R0
set_db inst:soc_clk_top_mirror_L2_inv1 .place_status fixed
connect soc_clk_top_mirror_L2_inv1/A -net soc_clk_top_mirror_L1_inv1_Y
connect soc_clk_top_mirror_L2_inv1/Y -net soc_clk_top_mirror_L2_inv1_Y

# ============================================================
# Step 21: Place and connect spine soc_clk_top level L3
# ============================================================

# soc_clk_top_L3_inv1  lower-left (5637.72, 13039.118) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_L3_inv1
place_inst soc_clk_top_L3_inv1 5637.72 13039.118 MX
set_db inst:soc_clk_top_L3_inv1 .place_status fixed
connect soc_clk_top_L3_inv1/A -net soc_clk_top_L2_inv1_Y
connect soc_clk_top_L3_inv1/Y -net soc_clk_top_L3_inv1_Y

# soc_clk_top_L3_inv2  lower-left (5637.72, 11739.4) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_L3_inv2
place_inst soc_clk_top_L3_inv2 5637.72 11739.4 R0
set_db inst:soc_clk_top_L3_inv2 .place_status fixed
connect soc_clk_top_L3_inv2/A -net soc_clk_top_L2_inv1_Y
connect soc_clk_top_L3_inv2/Y -net soc_clk_top_L3_inv2_Y

# soc_clk_top_mirror_L3_inv1  lower-left (5637.72, 9119.136) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_mirror_L3_inv1
place_inst soc_clk_top_mirror_L3_inv1 5637.72 9119.136 R0
set_db inst:soc_clk_top_mirror_L3_inv1 .place_status fixed
connect soc_clk_top_mirror_L3_inv1/A -net soc_clk_top_mirror_L2_inv1_Y
connect soc_clk_top_mirror_L3_inv1/Y -net soc_clk_top_mirror_L3_inv1_Y

# soc_clk_top_mirror_L3_inv2  lower-left (5637.72, 10419.362) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_top_mirror_L3_inv2
place_inst soc_clk_top_mirror_L3_inv2 5637.72 10419.362 MX
set_db inst:soc_clk_top_mirror_L3_inv2 .place_status fixed
connect soc_clk_top_mirror_L3_inv2/A -net soc_clk_top_mirror_L2_inv1_Y
connect soc_clk_top_mirror_L3_inv2/Y -net soc_clk_top_mirror_L3_inv2_Y

# ============================================================
# Step 22: Place and connect spine mgt_clk_hor1 level L1
# ============================================================

# mgt_clk_hor1_L1_inv1  lower-left (3058.44, 10072.144) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor1_L1_inv1
place_inst mgt_clk_hor1_L1_inv1 3058.44 10072.144 R0
set_db inst:mgt_clk_hor1_L1_inv1 .place_status fixed
connect mgt_clk_hor1_L1_inv1/A -net mgt_clk_hor1_fwd_clk_mgt_clk_hor1_Y
connect mgt_clk_hor1_L1_inv1/Y -net mgt_clk_hor1_L1_inv1_Y

# mgt_clk_hor1_mirror_L1_inv1  lower-left (3038.44, 10072.111) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor1_mirror_L1_inv1
place_inst mgt_clk_hor1_mirror_L1_inv1 3038.44 10072.111 MY
set_db inst:mgt_clk_hor1_mirror_L1_inv1 .place_status fixed
connect mgt_clk_hor1_mirror_L1_inv1/A -net mgt_clk_hor1_fwd_clk_mgt_clk_hor1_Y
connect mgt_clk_hor1_mirror_L1_inv1/Y -net mgt_clk_hor1_mirror_L1_inv1_Y

# ============================================================
# Step 23: Place and connect spine mgt_clk_hor1 level L2
# ============================================================

# mgt_clk_hor1_L2_inv1  lower-left (4358.46, 10075.192) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor1_L2_inv1
place_inst mgt_clk_hor1_L2_inv1 4358.46 10075.192 R0
set_db inst:mgt_clk_hor1_L2_inv1 .place_status fixed
connect mgt_clk_hor1_L2_inv1/A -net mgt_clk_hor1_L1_inv1_Y
connect mgt_clk_hor1_L2_inv1/Y -net mgt_clk_hor1_L2_inv1_Y

# mgt_clk_hor1_mirror_L2_inv1  lower-left (1738.44, 10074.991) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor1_mirror_L2_inv1
place_inst mgt_clk_hor1_mirror_L2_inv1 1738.44 10074.991 MY
set_db inst:mgt_clk_hor1_mirror_L2_inv1 .place_status fixed
connect mgt_clk_hor1_mirror_L2_inv1/A -net mgt_clk_hor1_mirror_L1_inv1_Y
connect mgt_clk_hor1_mirror_L2_inv1/Y -net mgt_clk_hor1_mirror_L2_inv1_Y

# ============================================================
# Step 24: Place and connect spine mgt_clk_hor1 level L3
# ============================================================

# mgt_clk_hor1_L3_inv1  lower-left (5008.44, 10077.732) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor1_L3_inv1
place_inst mgt_clk_hor1_L3_inv1 5008.44 10077.732 R0
set_db inst:mgt_clk_hor1_L3_inv1 .place_status fixed
connect mgt_clk_hor1_L3_inv1/A -net mgt_clk_hor1_L2_inv1_Y
connect mgt_clk_hor1_L3_inv1/Y -net mgt_clk_hor1_L3_inv1_Y

# mgt_clk_hor1_L3_inv2  lower-left (3708.42, 10077.732) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor1_L3_inv2
place_inst mgt_clk_hor1_L3_inv2 3708.42 10077.732 R0
set_db inst:mgt_clk_hor1_L3_inv2 .place_status fixed
connect mgt_clk_hor1_L3_inv2/A -net mgt_clk_hor1_L2_inv1_Y
connect mgt_clk_hor1_L3_inv2/Y -net mgt_clk_hor1_L3_inv2_Y

# mgt_clk_hor1_mirror_L3_inv1  lower-left (1088.44, 10077.871) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor1_mirror_L3_inv1
place_inst mgt_clk_hor1_mirror_L3_inv1 1088.44 10077.871 MY
set_db inst:mgt_clk_hor1_mirror_L3_inv1 .place_status fixed
connect mgt_clk_hor1_mirror_L3_inv1/A -net mgt_clk_hor1_mirror_L2_inv1_Y
connect mgt_clk_hor1_mirror_L3_inv1/Y -net mgt_clk_hor1_mirror_L3_inv1_Y

# mgt_clk_hor1_mirror_L3_inv2  lower-left (2388.44, 10077.871) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor1_mirror_L3_inv2
place_inst mgt_clk_hor1_mirror_L3_inv2 2388.44 10077.871 MY
set_db inst:mgt_clk_hor1_mirror_L3_inv2 .place_status fixed
connect mgt_clk_hor1_mirror_L3_inv2/A -net mgt_clk_hor1_mirror_L2_inv1_Y
connect mgt_clk_hor1_mirror_L3_inv2/Y -net mgt_clk_hor1_mirror_L3_inv2_Y

# ============================================================
# Step 25: Place and connect spine soc_clk_hor1 level L1
# ============================================================

# soc_clk_hor1_L1_inv1  lower-left (3058.44, 10061.984) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor1_L1_inv1
place_inst soc_clk_hor1_L1_inv1 3058.44 10061.984 R0
set_db inst:soc_clk_hor1_L1_inv1 .place_status fixed
connect soc_clk_hor1_L1_inv1/A -net soc_clk_hor1_fwd_clk_soc_clk_hor1_Y
connect soc_clk_hor1_L1_inv1/Y -net soc_clk_hor1_L1_inv1_Y

# soc_clk_hor1_mirror_L1_inv1  lower-left (3038.44, 10062.111) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor1_mirror_L1_inv1
place_inst soc_clk_hor1_mirror_L1_inv1 3038.44 10062.111 MY
set_db inst:soc_clk_hor1_mirror_L1_inv1 .place_status fixed
connect soc_clk_hor1_mirror_L1_inv1/A -net soc_clk_hor1_fwd_clk_soc_clk_hor1_Y
connect soc_clk_hor1_mirror_L1_inv1/Y -net soc_clk_hor1_mirror_L1_inv1_Y

# ============================================================
# Step 26: Place and connect spine soc_clk_hor1 level L2
# ============================================================

# soc_clk_hor1_L2_inv1  lower-left (4358.46, 10059.444) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor1_L2_inv1
place_inst soc_clk_hor1_L2_inv1 4358.46 10059.444 R0
set_db inst:soc_clk_hor1_L2_inv1 .place_status fixed
connect soc_clk_hor1_L2_inv1/A -net soc_clk_hor1_L1_inv1_Y
connect soc_clk_hor1_L2_inv1/Y -net soc_clk_hor1_L2_inv1_Y

# soc_clk_hor1_mirror_L2_inv1  lower-left (1738.44, 10059.231) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor1_mirror_L2_inv1
place_inst soc_clk_hor1_mirror_L2_inv1 1738.44 10059.231 MY
set_db inst:soc_clk_hor1_mirror_L2_inv1 .place_status fixed
connect soc_clk_hor1_mirror_L2_inv1/A -net soc_clk_hor1_mirror_L1_inv1_Y
connect soc_clk_hor1_mirror_L2_inv1/Y -net soc_clk_hor1_mirror_L2_inv1_Y

# ============================================================
# Step 27: Place and connect spine soc_clk_hor1 level L3
# ============================================================

# soc_clk_hor1_L3_inv1  lower-left (5008.44, 10056.396) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor1_L3_inv1
place_inst soc_clk_hor1_L3_inv1 5008.44 10056.396 R0
set_db inst:soc_clk_hor1_L3_inv1 .place_status fixed
connect soc_clk_hor1_L3_inv1/A -net soc_clk_hor1_L2_inv1_Y
connect soc_clk_hor1_L3_inv1/Y -net soc_clk_hor1_L3_inv1_Y

# soc_clk_hor1_L3_inv2  lower-left (3708.42, 10056.396) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor1_L3_inv2
place_inst soc_clk_hor1_L3_inv2 3708.42 10056.396 R0
set_db inst:soc_clk_hor1_L3_inv2 .place_status fixed
connect soc_clk_hor1_L3_inv2/A -net soc_clk_hor1_L2_inv1_Y
connect soc_clk_hor1_L3_inv2/Y -net soc_clk_hor1_L3_inv2_Y

# soc_clk_hor1_mirror_L3_inv1  lower-left (1088.44, 10056.351) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor1_mirror_L3_inv1
place_inst soc_clk_hor1_mirror_L3_inv1 1088.44 10056.351 MY
set_db inst:soc_clk_hor1_mirror_L3_inv1 .place_status fixed
connect soc_clk_hor1_mirror_L3_inv1/A -net soc_clk_hor1_mirror_L2_inv1_Y
connect soc_clk_hor1_mirror_L3_inv1/Y -net soc_clk_hor1_mirror_L3_inv1_Y

# soc_clk_hor1_mirror_L3_inv2  lower-left (2388.44, 10056.351) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor1_mirror_L3_inv2
place_inst soc_clk_hor1_mirror_L3_inv2 2388.44 10056.351 MY
set_db inst:soc_clk_hor1_mirror_L3_inv2 .place_status fixed
connect soc_clk_hor1_mirror_L3_inv2/A -net soc_clk_hor1_mirror_L2_inv1_Y
connect soc_clk_hor1_mirror_L3_inv2/Y -net soc_clk_hor1_mirror_L3_inv2_Y

# ============================================================
# Step 28: Place and connect spine mgt_clk_hor2 level L1
# ============================================================

# mgt_clk_hor2_L1_inv1  lower-left (3058.44, 8758.964) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor2_L1_inv1
place_inst mgt_clk_hor2_L1_inv1 3058.44 8758.964 R0
set_db inst:mgt_clk_hor2_L1_inv1 .place_status fixed
connect mgt_clk_hor2_L1_inv1/A -net mgt_clk_hor2_fwd_clk_mgt_clk_hor2_Y
connect mgt_clk_hor2_L1_inv1/Y -net mgt_clk_hor2_L1_inv1_Y

# mgt_clk_hor2_mirror_L1_inv1  lower-left (3038.44, 8759.111) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor2_mirror_L1_inv1
place_inst mgt_clk_hor2_mirror_L1_inv1 3038.44 8759.111 MY
set_db inst:mgt_clk_hor2_mirror_L1_inv1 .place_status fixed
connect mgt_clk_hor2_mirror_L1_inv1/A -net mgt_clk_hor2_fwd_clk_mgt_clk_hor2_Y
connect mgt_clk_hor2_mirror_L1_inv1/Y -net mgt_clk_hor2_mirror_L1_inv1_Y

# ============================================================
# Step 29: Place and connect spine mgt_clk_hor2 level L2
# ============================================================

# mgt_clk_hor2_L2_inv1  lower-left (4358.46, 8762.012) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor2_L2_inv1
place_inst mgt_clk_hor2_L2_inv1 4358.46 8762.012 R0
set_db inst:mgt_clk_hor2_L2_inv1 .place_status fixed
connect mgt_clk_hor2_L2_inv1/A -net mgt_clk_hor2_L1_inv1_Y
connect mgt_clk_hor2_L2_inv1/Y -net mgt_clk_hor2_L2_inv1_Y

# mgt_clk_hor2_mirror_L2_inv1  lower-left (1738.44, 8761.991) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor2_mirror_L2_inv1
place_inst mgt_clk_hor2_mirror_L2_inv1 1738.44 8761.991 MY
set_db inst:mgt_clk_hor2_mirror_L2_inv1 .place_status fixed
connect mgt_clk_hor2_mirror_L2_inv1/A -net mgt_clk_hor2_mirror_L1_inv1_Y
connect mgt_clk_hor2_mirror_L2_inv1/Y -net mgt_clk_hor2_mirror_L2_inv1_Y

# ============================================================
# Step 30: Place and connect spine mgt_clk_hor2 level L3
# ============================================================

# mgt_clk_hor2_L3_inv1  lower-left (5008.44, 8765.06) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor2_L3_inv1
place_inst mgt_clk_hor2_L3_inv1 5008.44 8765.06 R0
set_db inst:mgt_clk_hor2_L3_inv1 .place_status fixed
connect mgt_clk_hor2_L3_inv1/A -net mgt_clk_hor2_L2_inv1_Y
connect mgt_clk_hor2_L3_inv1/Y -net mgt_clk_hor2_L3_inv1_Y

# mgt_clk_hor2_L3_inv2  lower-left (3708.42, 8765.06) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor2_L3_inv2
place_inst mgt_clk_hor2_L3_inv2 3708.42 8765.06 R0
set_db inst:mgt_clk_hor2_L3_inv2 .place_status fixed
connect mgt_clk_hor2_L3_inv2/A -net mgt_clk_hor2_L2_inv1_Y
connect mgt_clk_hor2_L3_inv2/Y -net mgt_clk_hor2_L3_inv2_Y

# mgt_clk_hor2_mirror_L3_inv1  lower-left (1088.44, 8764.871) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor2_mirror_L3_inv1
place_inst mgt_clk_hor2_mirror_L3_inv1 1088.44 8764.871 MY
set_db inst:mgt_clk_hor2_mirror_L3_inv1 .place_status fixed
connect mgt_clk_hor2_mirror_L3_inv1/A -net mgt_clk_hor2_mirror_L2_inv1_Y
connect mgt_clk_hor2_mirror_L3_inv1/Y -net mgt_clk_hor2_mirror_L3_inv1_Y

# mgt_clk_hor2_mirror_L3_inv2  lower-left (2388.44, 8764.871) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor2_mirror_L3_inv2
place_inst mgt_clk_hor2_mirror_L3_inv2 2388.44 8764.871 MY
set_db inst:mgt_clk_hor2_mirror_L3_inv2 .place_status fixed
connect mgt_clk_hor2_mirror_L3_inv2/A -net mgt_clk_hor2_mirror_L2_inv1_Y
connect mgt_clk_hor2_mirror_L3_inv2/Y -net mgt_clk_hor2_mirror_L3_inv2_Y

# ============================================================
# Step 31: Place and connect spine soc_clk_hor2 level L1
# ============================================================

# soc_clk_hor2_L1_inv1  lower-left (3058.44, 8749.312) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor2_L1_inv1
place_inst soc_clk_hor2_L1_inv1 3058.44 8749.312 R0
set_db inst:soc_clk_hor2_L1_inv1 .place_status fixed
connect soc_clk_hor2_L1_inv1/A -net soc_clk_hor2_fwd_clk_soc_clk_hor2_Y
connect soc_clk_hor2_L1_inv1/Y -net soc_clk_hor2_L1_inv1_Y

# soc_clk_hor2_mirror_L1_inv1  lower-left (3038.44, 8749.111) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor2_mirror_L1_inv1
place_inst soc_clk_hor2_mirror_L1_inv1 3038.44 8749.111 MY
set_db inst:soc_clk_hor2_mirror_L1_inv1 .place_status fixed
connect soc_clk_hor2_mirror_L1_inv1/A -net soc_clk_hor2_fwd_clk_soc_clk_hor2_Y
connect soc_clk_hor2_mirror_L1_inv1/Y -net soc_clk_hor2_mirror_L1_inv1_Y

# ============================================================
# Step 32: Place and connect spine soc_clk_hor2 level L2
# ============================================================

# soc_clk_hor2_L2_inv1  lower-left (4358.46, 8746.264) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor2_L2_inv1
place_inst soc_clk_hor2_L2_inv1 4358.46 8746.264 R0
set_db inst:soc_clk_hor2_L2_inv1 .place_status fixed
connect soc_clk_hor2_L2_inv1/A -net soc_clk_hor2_L1_inv1_Y
connect soc_clk_hor2_L2_inv1/Y -net soc_clk_hor2_L2_inv1_Y

# soc_clk_hor2_mirror_L2_inv1  lower-left (1738.44, 8746.231) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor2_mirror_L2_inv1
place_inst soc_clk_hor2_mirror_L2_inv1 1738.44 8746.231 MY
set_db inst:soc_clk_hor2_mirror_L2_inv1 .place_status fixed
connect soc_clk_hor2_mirror_L2_inv1/A -net soc_clk_hor2_mirror_L1_inv1_Y
connect soc_clk_hor2_mirror_L2_inv1/Y -net soc_clk_hor2_mirror_L2_inv1_Y

# ============================================================
# Step 33: Place and connect spine soc_clk_hor2 level L3
# ============================================================

# soc_clk_hor2_L3_inv1  lower-left (5008.44, 8743.216) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor2_L3_inv1
place_inst soc_clk_hor2_L3_inv1 5008.44 8743.216 R0
set_db inst:soc_clk_hor2_L3_inv1 .place_status fixed
connect soc_clk_hor2_L3_inv1/A -net soc_clk_hor2_L2_inv1_Y
connect soc_clk_hor2_L3_inv1/Y -net soc_clk_hor2_L3_inv1_Y

# soc_clk_hor2_L3_inv2  lower-left (3708.42, 8743.216) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor2_L3_inv2
place_inst soc_clk_hor2_L3_inv2 3708.42 8743.216 R0
set_db inst:soc_clk_hor2_L3_inv2 .place_status fixed
connect soc_clk_hor2_L3_inv2/A -net soc_clk_hor2_L2_inv1_Y
connect soc_clk_hor2_L3_inv2/Y -net soc_clk_hor2_L3_inv2_Y

# soc_clk_hor2_mirror_L3_inv1  lower-left (1088.44, 8743.351) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor2_mirror_L3_inv1
place_inst soc_clk_hor2_mirror_L3_inv1 1088.44 8743.351 MY
set_db inst:soc_clk_hor2_mirror_L3_inv1 .place_status fixed
connect soc_clk_hor2_mirror_L3_inv1/A -net soc_clk_hor2_mirror_L2_inv1_Y
connect soc_clk_hor2_mirror_L3_inv1/Y -net soc_clk_hor2_mirror_L3_inv1_Y

# soc_clk_hor2_mirror_L3_inv2  lower-left (2388.44, 8743.351) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor2_mirror_L3_inv2
place_inst soc_clk_hor2_mirror_L3_inv2 2388.44 8743.351 MY
set_db inst:soc_clk_hor2_mirror_L3_inv2 .place_status fixed
connect soc_clk_hor2_mirror_L3_inv2/A -net soc_clk_hor2_mirror_L2_inv1_Y
connect soc_clk_hor2_mirror_L3_inv2/Y -net soc_clk_hor2_mirror_L3_inv2_Y

# ============================================================
# Step 34: Place and connect spine mgt_clk_hor3 level L1
# ============================================================

# mgt_clk_hor3_L1_inv1  lower-left (3058.44, 6214.9) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor3_L1_inv1
place_inst mgt_clk_hor3_L1_inv1 3058.44 6214.9 R0
set_db inst:mgt_clk_hor3_L1_inv1 .place_status fixed
connect mgt_clk_hor3_L1_inv1/A -net mgt_clk_hor3_fwd_clk_mgt_clk_hor3_Y
connect mgt_clk_hor3_L1_inv1/Y -net mgt_clk_hor3_L1_inv1_Y

# mgt_clk_hor3_mirror_L1_inv1  lower-left (3038.44, 6215.111) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor3_mirror_L1_inv1
place_inst mgt_clk_hor3_mirror_L1_inv1 3038.44 6215.111 MY
set_db inst:mgt_clk_hor3_mirror_L1_inv1 .place_status fixed
connect mgt_clk_hor3_mirror_L1_inv1/A -net mgt_clk_hor3_fwd_clk_mgt_clk_hor3_Y
connect mgt_clk_hor3_mirror_L1_inv1/Y -net mgt_clk_hor3_mirror_L1_inv1_Y

# ============================================================
# Step 35: Place and connect spine mgt_clk_hor3 level L2
# ============================================================

# mgt_clk_hor3_L2_inv1  lower-left (4358.46, 6217.948) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor3_L2_inv1
place_inst mgt_clk_hor3_L2_inv1 4358.46 6217.948 R0
set_db inst:mgt_clk_hor3_L2_inv1 .place_status fixed
connect mgt_clk_hor3_L2_inv1/A -net mgt_clk_hor3_L1_inv1_Y
connect mgt_clk_hor3_L2_inv1/Y -net mgt_clk_hor3_L2_inv1_Y

# mgt_clk_hor3_mirror_L2_inv1  lower-left (1738.44, 6217.991) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor3_mirror_L2_inv1
place_inst mgt_clk_hor3_mirror_L2_inv1 1738.44 6217.991 MY
set_db inst:mgt_clk_hor3_mirror_L2_inv1 .place_status fixed
connect mgt_clk_hor3_mirror_L2_inv1/A -net mgt_clk_hor3_mirror_L1_inv1_Y
connect mgt_clk_hor3_mirror_L2_inv1/Y -net mgt_clk_hor3_mirror_L2_inv1_Y

# ============================================================
# Step 36: Place and connect spine mgt_clk_hor3 level L3
# ============================================================

# mgt_clk_hor3_L3_inv1  lower-left (5008.44, 6220.996) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor3_L3_inv1
place_inst mgt_clk_hor3_L3_inv1 5008.44 6220.996 R0
set_db inst:mgt_clk_hor3_L3_inv1 .place_status fixed
connect mgt_clk_hor3_L3_inv1/A -net mgt_clk_hor3_L2_inv1_Y
connect mgt_clk_hor3_L3_inv1/Y -net mgt_clk_hor3_L3_inv1_Y

# mgt_clk_hor3_L3_inv2  lower-left (3708.42, 6220.996) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor3_L3_inv2
place_inst mgt_clk_hor3_L3_inv2 3708.42 6220.996 R0
set_db inst:mgt_clk_hor3_L3_inv2 .place_status fixed
connect mgt_clk_hor3_L3_inv2/A -net mgt_clk_hor3_L2_inv1_Y
connect mgt_clk_hor3_L3_inv2/Y -net mgt_clk_hor3_L3_inv2_Y

# mgt_clk_hor3_mirror_L3_inv1  lower-left (1088.44, 6220.871) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor3_mirror_L3_inv1
place_inst mgt_clk_hor3_mirror_L3_inv1 1088.44 6220.871 MY
set_db inst:mgt_clk_hor3_mirror_L3_inv1 .place_status fixed
connect mgt_clk_hor3_mirror_L3_inv1/A -net mgt_clk_hor3_mirror_L2_inv1_Y
connect mgt_clk_hor3_mirror_L3_inv1/Y -net mgt_clk_hor3_mirror_L3_inv1_Y

# mgt_clk_hor3_mirror_L3_inv2  lower-left (2388.44, 6220.871) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor3_mirror_L3_inv2
place_inst mgt_clk_hor3_mirror_L3_inv2 2388.44 6220.871 MY
set_db inst:mgt_clk_hor3_mirror_L3_inv2 .place_status fixed
connect mgt_clk_hor3_mirror_L3_inv2/A -net mgt_clk_hor3_mirror_L2_inv1_Y
connect mgt_clk_hor3_mirror_L3_inv2/Y -net mgt_clk_hor3_mirror_L3_inv2_Y

# ============================================================
# Step 37: Place and connect spine soc_clk_hor3 level L1
# ============================================================

# soc_clk_hor3_L1_inv1  lower-left (3058.44, 6205.248) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor3_L1_inv1
place_inst soc_clk_hor3_L1_inv1 3058.44 6205.248 R0
set_db inst:soc_clk_hor3_L1_inv1 .place_status fixed
connect soc_clk_hor3_L1_inv1/A -net soc_clk_hor3_fwd_clk_soc_clk_hor3_Y
connect soc_clk_hor3_L1_inv1/Y -net soc_clk_hor3_L1_inv1_Y

# soc_clk_hor3_mirror_L1_inv1  lower-left (3038.44, 6205.111) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor3_mirror_L1_inv1
place_inst soc_clk_hor3_mirror_L1_inv1 3038.44 6205.111 MY
set_db inst:soc_clk_hor3_mirror_L1_inv1 .place_status fixed
connect soc_clk_hor3_mirror_L1_inv1/A -net soc_clk_hor3_fwd_clk_soc_clk_hor3_Y
connect soc_clk_hor3_mirror_L1_inv1/Y -net soc_clk_hor3_mirror_L1_inv1_Y

# ============================================================
# Step 38: Place and connect spine soc_clk_hor3 level L2
# ============================================================

# soc_clk_hor3_L2_inv1  lower-left (4358.46, 6202.2) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor3_L2_inv1
place_inst soc_clk_hor3_L2_inv1 4358.46 6202.2 R0
set_db inst:soc_clk_hor3_L2_inv1 .place_status fixed
connect soc_clk_hor3_L2_inv1/A -net soc_clk_hor3_L1_inv1_Y
connect soc_clk_hor3_L2_inv1/Y -net soc_clk_hor3_L2_inv1_Y

# soc_clk_hor3_mirror_L2_inv1  lower-left (1738.44, 6202.231) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor3_mirror_L2_inv1
place_inst soc_clk_hor3_mirror_L2_inv1 1738.44 6202.231 MY
set_db inst:soc_clk_hor3_mirror_L2_inv1 .place_status fixed
connect soc_clk_hor3_mirror_L2_inv1/A -net soc_clk_hor3_mirror_L1_inv1_Y
connect soc_clk_hor3_mirror_L2_inv1/Y -net soc_clk_hor3_mirror_L2_inv1_Y

# ============================================================
# Step 39: Place and connect spine soc_clk_hor3 level L3
# ============================================================

# soc_clk_hor3_L3_inv1  lower-left (5008.44, 6199.152) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor3_L3_inv1
place_inst soc_clk_hor3_L3_inv1 5008.44 6199.152 R0
set_db inst:soc_clk_hor3_L3_inv1 .place_status fixed
connect soc_clk_hor3_L3_inv1/A -net soc_clk_hor3_L2_inv1_Y
connect soc_clk_hor3_L3_inv1/Y -net soc_clk_hor3_L3_inv1_Y

# soc_clk_hor3_L3_inv2  lower-left (3708.42, 6199.152) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor3_L3_inv2
place_inst soc_clk_hor3_L3_inv2 3708.42 6199.152 R0
set_db inst:soc_clk_hor3_L3_inv2 .place_status fixed
connect soc_clk_hor3_L3_inv2/A -net soc_clk_hor3_L2_inv1_Y
connect soc_clk_hor3_L3_inv2/Y -net soc_clk_hor3_L3_inv2_Y

# soc_clk_hor3_mirror_L3_inv1  lower-left (1088.44, 6199.351) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor3_mirror_L3_inv1
place_inst soc_clk_hor3_mirror_L3_inv1 1088.44 6199.351 MY
set_db inst:soc_clk_hor3_mirror_L3_inv1 .place_status fixed
connect soc_clk_hor3_mirror_L3_inv1/A -net soc_clk_hor3_mirror_L2_inv1_Y
connect soc_clk_hor3_mirror_L3_inv1/Y -net soc_clk_hor3_mirror_L3_inv1_Y

# soc_clk_hor3_mirror_L3_inv2  lower-left (2388.44, 6199.351) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor3_mirror_L3_inv2
place_inst soc_clk_hor3_mirror_L3_inv2 2388.44 6199.351 MY
set_db inst:soc_clk_hor3_mirror_L3_inv2 .place_status fixed
connect soc_clk_hor3_mirror_L3_inv2/A -net soc_clk_hor3_mirror_L2_inv1_Y
connect soc_clk_hor3_mirror_L3_inv2/Y -net soc_clk_hor3_mirror_L3_inv2_Y

# ============================================================
# Step 40: Place and connect spine mgt_clk_hor4 level L1
# ============================================================

# mgt_clk_hor4_L1_inv1  lower-left (3058.44, 3438.172) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor4_L1_inv1
place_inst mgt_clk_hor4_L1_inv1 3058.44 3438.172 R0
set_db inst:mgt_clk_hor4_L1_inv1 .place_status fixed
connect mgt_clk_hor4_L1_inv1/A -net mgt_clk_hor4_fwd_clk_mgt_clk_hor4_Y
connect mgt_clk_hor4_L1_inv1/Y -net mgt_clk_hor4_L1_inv1_Y

# mgt_clk_hor4_mirror_L1_inv1  lower-left (3038.44, 3438.111) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor4_mirror_L1_inv1
place_inst mgt_clk_hor4_mirror_L1_inv1 3038.44 3438.111 MY
set_db inst:mgt_clk_hor4_mirror_L1_inv1 .place_status fixed
connect mgt_clk_hor4_mirror_L1_inv1/A -net mgt_clk_hor4_fwd_clk_mgt_clk_hor4_Y
connect mgt_clk_hor4_mirror_L1_inv1/Y -net mgt_clk_hor4_mirror_L1_inv1_Y

# ============================================================
# Step 41: Place and connect spine mgt_clk_hor4 level L2
# ============================================================

# mgt_clk_hor4_L2_inv1  lower-left (4358.46, 3441.22) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor4_L2_inv1
place_inst mgt_clk_hor4_L2_inv1 4358.46 3441.22 R0
set_db inst:mgt_clk_hor4_L2_inv1 .place_status fixed
connect mgt_clk_hor4_L2_inv1/A -net mgt_clk_hor4_L1_inv1_Y
connect mgt_clk_hor4_L2_inv1/Y -net mgt_clk_hor4_L2_inv1_Y

# mgt_clk_hor4_mirror_L2_inv1  lower-left (1738.44, 3440.991) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor4_mirror_L2_inv1
place_inst mgt_clk_hor4_mirror_L2_inv1 1738.44 3440.991 MY
set_db inst:mgt_clk_hor4_mirror_L2_inv1 .place_status fixed
connect mgt_clk_hor4_mirror_L2_inv1/A -net mgt_clk_hor4_mirror_L1_inv1_Y
connect mgt_clk_hor4_mirror_L2_inv1/Y -net mgt_clk_hor4_mirror_L2_inv1_Y

# ============================================================
# Step 42: Place and connect spine mgt_clk_hor4 level L3
# ============================================================

# mgt_clk_hor4_L3_inv1  lower-left (5008.44, 3443.76) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor4_L3_inv1
place_inst mgt_clk_hor4_L3_inv1 5008.44 3443.76 R0
set_db inst:mgt_clk_hor4_L3_inv1 .place_status fixed
connect mgt_clk_hor4_L3_inv1/A -net mgt_clk_hor4_L2_inv1_Y
connect mgt_clk_hor4_L3_inv1/Y -net mgt_clk_hor4_L3_inv1_Y

# mgt_clk_hor4_L3_inv2  lower-left (3708.42, 3443.76) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor4_L3_inv2
place_inst mgt_clk_hor4_L3_inv2 3708.42 3443.76 R0
set_db inst:mgt_clk_hor4_L3_inv2 .place_status fixed
connect mgt_clk_hor4_L3_inv2/A -net mgt_clk_hor4_L2_inv1_Y
connect mgt_clk_hor4_L3_inv2/Y -net mgt_clk_hor4_L3_inv2_Y

# mgt_clk_hor4_mirror_L3_inv1  lower-left (1088.44, 3443.871) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor4_mirror_L3_inv1
place_inst mgt_clk_hor4_mirror_L3_inv1 1088.44 3443.871 MY
set_db inst:mgt_clk_hor4_mirror_L3_inv1 .place_status fixed
connect mgt_clk_hor4_mirror_L3_inv1/A -net mgt_clk_hor4_mirror_L2_inv1_Y
connect mgt_clk_hor4_mirror_L3_inv1/Y -net mgt_clk_hor4_mirror_L3_inv1_Y

# mgt_clk_hor4_mirror_L3_inv2  lower-left (2388.44, 3443.871) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor4_mirror_L3_inv2
place_inst mgt_clk_hor4_mirror_L3_inv2 2388.44 3443.871 MY
set_db inst:mgt_clk_hor4_mirror_L3_inv2 .place_status fixed
connect mgt_clk_hor4_mirror_L3_inv2/A -net mgt_clk_hor4_mirror_L2_inv1_Y
connect mgt_clk_hor4_mirror_L3_inv2/Y -net mgt_clk_hor4_mirror_L3_inv2_Y

# ============================================================
# Step 43: Place and connect spine soc_clk_hor4 level L1
# ============================================================

# soc_clk_hor4_L1_inv1  lower-left (3058.44, 3428.012) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor4_L1_inv1
place_inst soc_clk_hor4_L1_inv1 3058.44 3428.012 R0
set_db inst:soc_clk_hor4_L1_inv1 .place_status fixed
connect soc_clk_hor4_L1_inv1/A -net soc_clk_hor4_fwd_clk_soc_clk_hor4_Y
connect soc_clk_hor4_L1_inv1/Y -net soc_clk_hor4_L1_inv1_Y

# soc_clk_hor4_mirror_L1_inv1  lower-left (3038.44, 3428.111) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor4_mirror_L1_inv1
place_inst soc_clk_hor4_mirror_L1_inv1 3038.44 3428.111 MY
set_db inst:soc_clk_hor4_mirror_L1_inv1 .place_status fixed
connect soc_clk_hor4_mirror_L1_inv1/A -net soc_clk_hor4_fwd_clk_soc_clk_hor4_Y
connect soc_clk_hor4_mirror_L1_inv1/Y -net soc_clk_hor4_mirror_L1_inv1_Y

# ============================================================
# Step 44: Place and connect spine soc_clk_hor4 level L2
# ============================================================

# soc_clk_hor4_L2_inv1  lower-left (4358.46, 3425.472) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor4_L2_inv1
place_inst soc_clk_hor4_L2_inv1 4358.46 3425.472 R0
set_db inst:soc_clk_hor4_L2_inv1 .place_status fixed
connect soc_clk_hor4_L2_inv1/A -net soc_clk_hor4_L1_inv1_Y
connect soc_clk_hor4_L2_inv1/Y -net soc_clk_hor4_L2_inv1_Y

# soc_clk_hor4_mirror_L2_inv1  lower-left (1738.44, 3425.231) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor4_mirror_L2_inv1
place_inst soc_clk_hor4_mirror_L2_inv1 1738.44 3425.231 MY
set_db inst:soc_clk_hor4_mirror_L2_inv1 .place_status fixed
connect soc_clk_hor4_mirror_L2_inv1/A -net soc_clk_hor4_mirror_L1_inv1_Y
connect soc_clk_hor4_mirror_L2_inv1/Y -net soc_clk_hor4_mirror_L2_inv1_Y

# ============================================================
# Step 45: Place and connect spine soc_clk_hor4 level L3
# ============================================================

# soc_clk_hor4_L3_inv1  lower-left (5008.44, 3422.424) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor4_L3_inv1
place_inst soc_clk_hor4_L3_inv1 5008.44 3422.424 R0
set_db inst:soc_clk_hor4_L3_inv1 .place_status fixed
connect soc_clk_hor4_L3_inv1/A -net soc_clk_hor4_L2_inv1_Y
connect soc_clk_hor4_L3_inv1/Y -net soc_clk_hor4_L3_inv1_Y

# soc_clk_hor4_L3_inv2  lower-left (3708.42, 3422.424) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor4_L3_inv2
place_inst soc_clk_hor4_L3_inv2 3708.42 3422.424 R0
set_db inst:soc_clk_hor4_L3_inv2 .place_status fixed
connect soc_clk_hor4_L3_inv2/A -net soc_clk_hor4_L2_inv1_Y
connect soc_clk_hor4_L3_inv2/Y -net soc_clk_hor4_L3_inv2_Y

# soc_clk_hor4_mirror_L3_inv1  lower-left (1088.44, 3422.351) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor4_mirror_L3_inv1
place_inst soc_clk_hor4_mirror_L3_inv1 1088.44 3422.351 MY
set_db inst:soc_clk_hor4_mirror_L3_inv1 .place_status fixed
connect soc_clk_hor4_mirror_L3_inv1/A -net soc_clk_hor4_mirror_L2_inv1_Y
connect soc_clk_hor4_mirror_L3_inv1/Y -net soc_clk_hor4_mirror_L3_inv1_Y

# soc_clk_hor4_mirror_L3_inv2  lower-left (2388.44, 3422.351) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor4_mirror_L3_inv2
place_inst soc_clk_hor4_mirror_L3_inv2 2388.44 3422.351 MY
set_db inst:soc_clk_hor4_mirror_L3_inv2 .place_status fixed
connect soc_clk_hor4_mirror_L3_inv2/A -net soc_clk_hor4_mirror_L2_inv1_Y
connect soc_clk_hor4_mirror_L3_inv2/Y -net soc_clk_hor4_mirror_L3_inv2_Y

# ============================================================
# Step 46: Place and connect spine mgt_clk_hor5 level L1
# ============================================================

# mgt_clk_hor5_L1_inv1  lower-left (3058.44, 893.092) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor5_L1_inv1
place_inst mgt_clk_hor5_L1_inv1 3058.44 893.092 R0
set_db inst:mgt_clk_hor5_L1_inv1 .place_status fixed
connect mgt_clk_hor5_L1_inv1/A -net mgt_clk_hor5_fwd_clk_mgt_clk_hor5_Y
connect mgt_clk_hor5_L1_inv1/Y -net mgt_clk_hor5_L1_inv1_Y

# mgt_clk_hor5_mirror_L1_inv1  lower-left (3038.44, 893.111) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor5_mirror_L1_inv1
place_inst mgt_clk_hor5_mirror_L1_inv1 3038.44 893.111 MY
set_db inst:mgt_clk_hor5_mirror_L1_inv1 .place_status fixed
connect mgt_clk_hor5_mirror_L1_inv1/A -net mgt_clk_hor5_fwd_clk_mgt_clk_hor5_Y
connect mgt_clk_hor5_mirror_L1_inv1/Y -net mgt_clk_hor5_mirror_L1_inv1_Y

# ============================================================
# Step 47: Place and connect spine mgt_clk_hor5 level L2
# ============================================================

# mgt_clk_hor5_L2_inv1  lower-left (4358.46, 896.14) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor5_L2_inv1
place_inst mgt_clk_hor5_L2_inv1 4358.46 896.14 R0
set_db inst:mgt_clk_hor5_L2_inv1 .place_status fixed
connect mgt_clk_hor5_L2_inv1/A -net mgt_clk_hor5_L1_inv1_Y
connect mgt_clk_hor5_L2_inv1/Y -net mgt_clk_hor5_L2_inv1_Y

# mgt_clk_hor5_mirror_L2_inv1  lower-left (1738.44, 895.991) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor5_mirror_L2_inv1
place_inst mgt_clk_hor5_mirror_L2_inv1 1738.44 895.991 MY
set_db inst:mgt_clk_hor5_mirror_L2_inv1 .place_status fixed
connect mgt_clk_hor5_mirror_L2_inv1/A -net mgt_clk_hor5_mirror_L1_inv1_Y
connect mgt_clk_hor5_mirror_L2_inv1/Y -net mgt_clk_hor5_mirror_L2_inv1_Y

# ============================================================
# Step 48: Place and connect spine mgt_clk_hor5 level L3
# ============================================================

# mgt_clk_hor5_L3_inv1  lower-left (5008.44, 898.68) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor5_L3_inv1
place_inst mgt_clk_hor5_L3_inv1 5008.44 898.68 R0
set_db inst:mgt_clk_hor5_L3_inv1 .place_status fixed
connect mgt_clk_hor5_L3_inv1/A -net mgt_clk_hor5_L2_inv1_Y
connect mgt_clk_hor5_L3_inv1/Y -net mgt_clk_hor5_L3_inv1_Y

# mgt_clk_hor5_L3_inv2  lower-left (3708.42, 898.68) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor5_L3_inv2
place_inst mgt_clk_hor5_L3_inv2 3708.42 898.68 R0
set_db inst:mgt_clk_hor5_L3_inv2 .place_status fixed
connect mgt_clk_hor5_L3_inv2/A -net mgt_clk_hor5_L2_inv1_Y
connect mgt_clk_hor5_L3_inv2/Y -net mgt_clk_hor5_L3_inv2_Y

# mgt_clk_hor5_mirror_L3_inv1  lower-left (1088.44, 898.871) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor5_mirror_L3_inv1
place_inst mgt_clk_hor5_mirror_L3_inv1 1088.44 898.871 MY
set_db inst:mgt_clk_hor5_mirror_L3_inv1 .place_status fixed
connect mgt_clk_hor5_mirror_L3_inv1/A -net mgt_clk_hor5_mirror_L2_inv1_Y
connect mgt_clk_hor5_mirror_L3_inv1/Y -net mgt_clk_hor5_mirror_L3_inv1_Y

# mgt_clk_hor5_mirror_L3_inv2  lower-left (2388.44, 898.871) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor5_mirror_L3_inv2
place_inst mgt_clk_hor5_mirror_L3_inv2 2388.44 898.871 MY
set_db inst:mgt_clk_hor5_mirror_L3_inv2 .place_status fixed
connect mgt_clk_hor5_mirror_L3_inv2/A -net mgt_clk_hor5_mirror_L2_inv1_Y
connect mgt_clk_hor5_mirror_L3_inv2/Y -net mgt_clk_hor5_mirror_L3_inv2_Y

# ============================================================
# Step 49: Place and connect spine soc_clk_hor5 level L1
# ============================================================

# soc_clk_hor5_L1_inv1  lower-left (3058.44, 882.932) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor5_L1_inv1
place_inst soc_clk_hor5_L1_inv1 3058.44 882.932 R0
set_db inst:soc_clk_hor5_L1_inv1 .place_status fixed
connect soc_clk_hor5_L1_inv1/A -net soc_clk_hor5_fwd_clk_soc_clk_hor5_Y
connect soc_clk_hor5_L1_inv1/Y -net soc_clk_hor5_L1_inv1_Y

# soc_clk_hor5_mirror_L1_inv1  lower-left (3038.44, 883.111) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor5_mirror_L1_inv1
place_inst soc_clk_hor5_mirror_L1_inv1 3038.44 883.111 MY
set_db inst:soc_clk_hor5_mirror_L1_inv1 .place_status fixed
connect soc_clk_hor5_mirror_L1_inv1/A -net soc_clk_hor5_fwd_clk_soc_clk_hor5_Y
connect soc_clk_hor5_mirror_L1_inv1/Y -net soc_clk_hor5_mirror_L1_inv1_Y

# ============================================================
# Step 50: Place and connect spine soc_clk_hor5 level L2
# ============================================================

# soc_clk_hor5_L2_inv1  lower-left (4358.46, 880.392) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor5_L2_inv1
place_inst soc_clk_hor5_L2_inv1 4358.46 880.392 R0
set_db inst:soc_clk_hor5_L2_inv1 .place_status fixed
connect soc_clk_hor5_L2_inv1/A -net soc_clk_hor5_L1_inv1_Y
connect soc_clk_hor5_L2_inv1/Y -net soc_clk_hor5_L2_inv1_Y

# soc_clk_hor5_mirror_L2_inv1  lower-left (1738.44, 880.231) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor5_mirror_L2_inv1
place_inst soc_clk_hor5_mirror_L2_inv1 1738.44 880.231 MY
set_db inst:soc_clk_hor5_mirror_L2_inv1 .place_status fixed
connect soc_clk_hor5_mirror_L2_inv1/A -net soc_clk_hor5_mirror_L1_inv1_Y
connect soc_clk_hor5_mirror_L2_inv1/Y -net soc_clk_hor5_mirror_L2_inv1_Y

# ============================================================
# Step 51: Place and connect spine soc_clk_hor5 level L3
# ============================================================

# soc_clk_hor5_L3_inv1  lower-left (5008.44, 877.344) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor5_L3_inv1
place_inst soc_clk_hor5_L3_inv1 5008.44 877.344 R0
set_db inst:soc_clk_hor5_L3_inv1 .place_status fixed
connect soc_clk_hor5_L3_inv1/A -net soc_clk_hor5_L2_inv1_Y
connect soc_clk_hor5_L3_inv1/Y -net soc_clk_hor5_L3_inv1_Y

# soc_clk_hor5_L3_inv2  lower-left (3708.42, 877.344) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor5_L3_inv2
place_inst soc_clk_hor5_L3_inv2 3708.42 877.344 R0
set_db inst:soc_clk_hor5_L3_inv2 .place_status fixed
connect soc_clk_hor5_L3_inv2/A -net soc_clk_hor5_L2_inv1_Y
connect soc_clk_hor5_L3_inv2/Y -net soc_clk_hor5_L3_inv2_Y

# soc_clk_hor5_mirror_L3_inv1  lower-left (1088.44, 877.351) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor5_mirror_L3_inv1
place_inst soc_clk_hor5_mirror_L3_inv1 1088.44 877.351 MY
set_db inst:soc_clk_hor5_mirror_L3_inv1 .place_status fixed
connect soc_clk_hor5_mirror_L3_inv1/A -net soc_clk_hor5_mirror_L2_inv1_Y
connect soc_clk_hor5_mirror_L3_inv1/Y -net soc_clk_hor5_mirror_L3_inv1_Y

# soc_clk_hor5_mirror_L3_inv2  lower-left (2388.44, 877.351) um, FN
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor5_mirror_L3_inv2
place_inst soc_clk_hor5_mirror_L3_inv2 2388.44 877.351 MY
set_db inst:soc_clk_hor5_mirror_L3_inv2 .place_status fixed
connect soc_clk_hor5_mirror_L3_inv2/A -net soc_clk_hor5_mirror_L2_inv1_Y
connect soc_clk_hor5_mirror_L3_inv2/Y -net soc_clk_hor5_mirror_L3_inv2_Y

# ============================================================
# Step 52: Other instances (create_inst)
# ============================================================

# mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_1  lower-left (5696.88, 13612.396) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_1
place_inst mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_1 5696.88 13612.396 R0
set_db inst:mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_1 .place_status fixed
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_1/A -net mgt_clk_ione_ctm2_clk_out_31_2_clock
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_1/Y -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_1_Y

# mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_2  lower-left (5696.88, 12612.652) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_2
place_inst mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_2 5696.88 12612.652 R0
set_db inst:mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_2 .place_status fixed
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_2/A -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_1_Y
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_2/Y -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_2_Y

# mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_3  lower-left (5696.88, 11612.4) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_3
place_inst mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_3 5696.88 11612.4 R0
set_db inst:mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_3 .place_status fixed
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_3/A -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_2_Y
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_3/Y -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_3_Y

# mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_4  lower-left (5696.88, 10612.656) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_4
place_inst mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_4 5696.88 10612.656 R0
set_db inst:mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_4 .place_status fixed
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_4/A -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_3_Y
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_4/Y -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_4_Y

# mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_5  lower-left (5696.88, 9612.404) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_5
place_inst mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_5 5696.88 9612.404 R0
set_db inst:mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_5 .place_status fixed
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_5/A -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_4_Y
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_5/Y -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_5_Y

# mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_6  lower-left (5696.88, 8612.66) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_6
place_inst mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_6 5696.88 8612.66 R0
set_db inst:mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_6 .place_status fixed
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_6/A -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_5_Y
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_6/Y -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_6_Y

# mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_7  lower-left (5696.88, 7612.408) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_7
place_inst mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_7 5696.88 7612.408 R0
set_db inst:mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_7 .place_status fixed
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_7/A -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_6_Y
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_7/Y -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_7_Y

# mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_8  lower-left (5696.88, 6612.664) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_8
place_inst mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_8 5696.88 6612.664 R0
set_db inst:mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_8 .place_status fixed
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_8/A -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_7_Y
connect mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_8/Y -net mgt_clk_ione_ctm2_clk_out_31_2_clock_buf_8_Y

# soc_clk_ione_ctm4_clk_out_31_4_clock_buf_1  lower-left (5662.32, 13649.988) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_1
place_inst soc_clk_ione_ctm4_clk_out_31_4_clock_buf_1 5662.32 13649.988 R0
set_db inst:soc_clk_ione_ctm4_clk_out_31_4_clock_buf_1 .place_status fixed
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_1/A -net soc_clk_ione_ctm4_clk_out_31_4_clock
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_1/Y -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_1_Y

# soc_clk_ione_ctm4_clk_out_31_4_clock_buf_2  lower-left (5662.32, 12650.244) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_2
place_inst soc_clk_ione_ctm4_clk_out_31_4_clock_buf_2 5662.32 12650.244 R0
set_db inst:soc_clk_ione_ctm4_clk_out_31_4_clock_buf_2 .place_status fixed
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_2/A -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_1_Y
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_2/Y -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_2_Y

# soc_clk_ione_ctm4_clk_out_31_4_clock_buf_3  lower-left (5662.32, 11649.992) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_3
place_inst soc_clk_ione_ctm4_clk_out_31_4_clock_buf_3 5662.32 11649.992 R0
set_db inst:soc_clk_ione_ctm4_clk_out_31_4_clock_buf_3 .place_status fixed
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_3/A -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_2_Y
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_3/Y -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_3_Y

# soc_clk_ione_ctm4_clk_out_31_4_clock_buf_4  lower-left (5662.32, 10650.248) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_4
place_inst soc_clk_ione_ctm4_clk_out_31_4_clock_buf_4 5662.32 10650.248 R0
set_db inst:soc_clk_ione_ctm4_clk_out_31_4_clock_buf_4 .place_status fixed
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_4/A -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_3_Y
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_4/Y -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_4_Y

# soc_clk_ione_ctm4_clk_out_31_4_clock_buf_5  lower-left (5662.32, 9649.996) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_5
place_inst soc_clk_ione_ctm4_clk_out_31_4_clock_buf_5 5662.32 9649.996 R0
set_db inst:soc_clk_ione_ctm4_clk_out_31_4_clock_buf_5 .place_status fixed
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_5/A -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_4_Y
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_5/Y -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_5_Y

# soc_clk_ione_ctm4_clk_out_31_4_clock_buf_6  lower-left (5662.32, 8650.252) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_6
place_inst soc_clk_ione_ctm4_clk_out_31_4_clock_buf_6 5662.32 8650.252 R0
set_db inst:soc_clk_ione_ctm4_clk_out_31_4_clock_buf_6 .place_status fixed
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_6/A -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_5_Y
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_6/Y -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_6_Y

# soc_clk_ione_ctm4_clk_out_31_4_clock_buf_7  lower-left (5662.32, 7650) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_7
place_inst soc_clk_ione_ctm4_clk_out_31_4_clock_buf_7 5662.32 7650 R0
set_db inst:soc_clk_ione_ctm4_clk_out_31_4_clock_buf_7 .place_status fixed
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_7/A -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_6_Y
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_7/Y -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_7_Y

# soc_clk_ione_ctm4_clk_out_31_4_clock_buf_8  lower-left (5662.32, 6650.256) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_ione_ctm4_clk_out_31_4_clock_buf_8
place_inst soc_clk_ione_ctm4_clk_out_31_4_clock_buf_8 5662.32 6650.256 R0
set_db inst:soc_clk_ione_ctm4_clk_out_31_4_clock_buf_8 .place_status fixed
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_8/A -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_7_Y
connect soc_clk_ione_ctm4_clk_out_31_4_clock_buf_8/Y -net soc_clk_ione_ctm4_clk_out_31_4_clock_buf_8_Y

# spine_connect_bot_mgt_clk_clk_spine_bot  lower-left (5591.28, 2108.99) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_bot_mgt_clk_clk_spine_bot
place_inst spine_connect_bot_mgt_clk_clk_spine_bot 5591.28 2108.99 MX
set_db inst:spine_connect_bot_mgt_clk_clk_spine_bot .place_status fixed
connect spine_connect_bot_mgt_clk_clk_spine_bot/A -net mgt_clk_main_mirror_L4_inv1_Y
connect spine_connect_bot_mgt_clk_clk_spine_bot/Y -net spine_connect_bot_mgt_clk_clk_spine_bot_Y

# mid_buffer_1  lower-left (5584.56, 1676.428) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mid_buffer_1
place_inst mid_buffer_1 5584.56 1676.428 R0
set_db inst:mid_buffer_1 .place_status fixed
connect mid_buffer_1/A -net spine_connect_bot_mgt_clk_clk_spine_bot_Y
connect mid_buffer_1/Y -net mid_buffer_1_Y

# spine_connect_top_mgt_clk_clk_spine_top  lower-left (5682.78, 10441.206) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_top_mgt_clk_clk_spine_top
place_inst spine_connect_top_mgt_clk_clk_spine_top 5682.78 10441.206 MX
set_db inst:spine_connect_top_mgt_clk_clk_spine_top .place_status fixed
connect spine_connect_top_mgt_clk_clk_spine_top/A -net mgt_clk_main_L4_inv1_Y
connect spine_connect_top_mgt_clk_clk_spine_top/Y -net spine_connect_top_mgt_clk_clk_spine_top_Y

# mid_buffer_2  lower-left (5679.6, 11756.418) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mid_buffer_2
place_inst mid_buffer_2 5679.6 11756.418 MX
set_db inst:mid_buffer_2 .place_status fixed
connect mid_buffer_2/A -net spine_connect_top_mgt_clk_clk_spine_top_Y
connect mid_buffer_2/Y -net mid_buffer_2_Y

# spine_connect_bot_soc_clk_bot  lower-left (5556.72, 2143.534) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_bot_soc_clk_bot
place_inst spine_connect_bot_soc_clk_bot 5556.72 2143.534 MX
set_db inst:spine_connect_bot_soc_clk_bot .place_status fixed
connect spine_connect_bot_soc_clk_bot/A -net soc_clk_main_mirror_L4_inv1_Y
connect spine_connect_bot_soc_clk_bot/Y -net spine_connect_bot_soc_clk_bot_Y

# mid_buffer_3  lower-left (5550, 1710.972) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mid_buffer_3
place_inst mid_buffer_3 5550 1710.972 R0
set_db inst:mid_buffer_3 .place_status fixed
connect mid_buffer_3/A -net spine_connect_bot_soc_clk_bot_Y
connect mid_buffer_3/Y -net mid_buffer_3_Y

# spine_connect_top_soc_clk_top  lower-left (5648.22, 10475.75) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_top_soc_clk_top
place_inst spine_connect_top_soc_clk_top 5648.22 10475.75 MX
set_db inst:spine_connect_top_soc_clk_top .place_status fixed
connect spine_connect_top_soc_clk_top/A -net soc_clk_main_L4_inv1_Y
connect spine_connect_top_soc_clk_top/Y -net spine_connect_top_soc_clk_top_Y

# mid_buffer_4  lower-left (5645.04, 11790.962) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mid_buffer_4
place_inst mid_buffer_4 5645.04 11790.962 MX
set_db inst:mid_buffer_4 .place_status fixed
connect mid_buffer_4/A -net spine_connect_top_soc_clk_top_Y
connect mid_buffer_4/Y -net mid_buffer_4_Y

# mgt_clk_hor1_fwd_clk_mgt_clk_hor1  lower-left (5677.74, 10071.89) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor1_fwd_clk_mgt_clk_hor1
place_inst mgt_clk_hor1_fwd_clk_mgt_clk_hor1 5677.74 10071.89 MX
set_db inst:mgt_clk_hor1_fwd_clk_mgt_clk_hor1 .place_status fixed
connect mgt_clk_hor1_fwd_clk_mgt_clk_hor1/A -net mgt_clk_main_L4_inv1_Y
connect mgt_clk_hor1_fwd_clk_mgt_clk_hor1/Y -net mgt_clk_hor1_fwd_clk_mgt_clk_hor1_Y

# mgt_clk_hor2_fwd_clk_mgt_clk_hor2  lower-left (5677.74, 8759.218) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor2_fwd_clk_mgt_clk_hor2
place_inst mgt_clk_hor2_fwd_clk_mgt_clk_hor2 5677.74 8759.218 MX
set_db inst:mgt_clk_hor2_fwd_clk_mgt_clk_hor2 .place_status fixed
connect mgt_clk_hor2_fwd_clk_mgt_clk_hor2/A -net mgt_clk_main_L4_inv2_Y
connect mgt_clk_hor2_fwd_clk_mgt_clk_hor2/Y -net mgt_clk_hor2_fwd_clk_mgt_clk_hor2_Y

# mgt_clk_hor3_fwd_clk_mgt_clk_hor3  lower-left (5677.74, 6214.9) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor3_fwd_clk_mgt_clk_hor3
place_inst mgt_clk_hor3_fwd_clk_mgt_clk_hor3 5677.74 6214.9 R0
set_db inst:mgt_clk_hor3_fwd_clk_mgt_clk_hor3 .place_status fixed
connect mgt_clk_hor3_fwd_clk_mgt_clk_hor3/A -net mgt_clk_main_L4_inv4_Y
connect mgt_clk_hor3_fwd_clk_mgt_clk_hor3/Y -net mgt_clk_hor3_fwd_clk_mgt_clk_hor3_Y

# mgt_clk_hor4_fwd_clk_mgt_clk_hor4  lower-left (5589.9, 3390.42) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor4_fwd_clk_mgt_clk_hor4
place_inst mgt_clk_hor4_fwd_clk_mgt_clk_hor4 5589.9 3390.42 R0
set_db inst:mgt_clk_hor4_fwd_clk_mgt_clk_hor4 .place_status fixed
connect mgt_clk_hor4_fwd_clk_mgt_clk_hor4/A -net mgt_clk_main_mirror_L4_inv3_Y
connect mgt_clk_hor4_fwd_clk_mgt_clk_hor4/Y -net mgt_clk_hor4_fwd_clk_mgt_clk_hor4_Y

# mgt_clk_hor5_fwd_clk_mgt_clk_hor5  lower-left (5589.9, 913.92) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name mgt_clk_hor5_fwd_clk_mgt_clk_hor5
place_inst mgt_clk_hor5_fwd_clk_mgt_clk_hor5 5589.9 913.92 R0
set_db inst:mgt_clk_hor5_fwd_clk_mgt_clk_hor5 .place_status fixed
connect mgt_clk_hor5_fwd_clk_mgt_clk_hor5/A -net mgt_clk_main_mirror_L4_inv1_Y
connect mgt_clk_hor5_fwd_clk_mgt_clk_hor5/Y -net mgt_clk_hor5_fwd_clk_mgt_clk_hor5_Y

# soc_clk_hor1_fwd_clk_soc_clk_hor1  lower-left (5643.18, 10062.238) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor1_fwd_clk_soc_clk_hor1
place_inst soc_clk_hor1_fwd_clk_soc_clk_hor1 5643.18 10062.238 MX
set_db inst:soc_clk_hor1_fwd_clk_soc_clk_hor1 .place_status fixed
connect soc_clk_hor1_fwd_clk_soc_clk_hor1/A -net soc_clk_main_L4_inv1_Y
connect soc_clk_hor1_fwd_clk_soc_clk_hor1/Y -net soc_clk_hor1_fwd_clk_soc_clk_hor1_Y

# soc_clk_hor2_fwd_clk_soc_clk_hor2  lower-left (5643.18, 8749.058) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor2_fwd_clk_soc_clk_hor2
place_inst soc_clk_hor2_fwd_clk_soc_clk_hor2 5643.18 8749.058 MX
set_db inst:soc_clk_hor2_fwd_clk_soc_clk_hor2 .place_status fixed
connect soc_clk_hor2_fwd_clk_soc_clk_hor2/A -net soc_clk_main_L4_inv2_Y
connect soc_clk_hor2_fwd_clk_soc_clk_hor2/Y -net soc_clk_hor2_fwd_clk_soc_clk_hor2_Y

# soc_clk_hor3_fwd_clk_soc_clk_hor3  lower-left (5643.18, 6205.248) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor3_fwd_clk_soc_clk_hor3
place_inst soc_clk_hor3_fwd_clk_soc_clk_hor3 5643.18 6205.248 R0
set_db inst:soc_clk_hor3_fwd_clk_soc_clk_hor3 .place_status fixed
connect soc_clk_hor3_fwd_clk_soc_clk_hor3/A -net soc_clk_main_L4_inv4_Y
connect soc_clk_hor3_fwd_clk_soc_clk_hor3/Y -net soc_clk_hor3_fwd_clk_soc_clk_hor3_Y

# soc_clk_hor4_fwd_clk_soc_clk_hor4  lower-left (5555.34, 3425.472) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor4_fwd_clk_soc_clk_hor4
place_inst soc_clk_hor4_fwd_clk_soc_clk_hor4 5555.34 3425.472 R0
set_db inst:soc_clk_hor4_fwd_clk_soc_clk_hor4 .place_status fixed
connect soc_clk_hor4_fwd_clk_soc_clk_hor4/A -net soc_clk_main_mirror_L4_inv3_Y
connect soc_clk_hor4_fwd_clk_soc_clk_hor4/Y -net soc_clk_hor4_fwd_clk_soc_clk_hor4_Y

# soc_clk_hor5_fwd_clk_soc_clk_hor5  lower-left (5555.34, 948.464) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name soc_clk_hor5_fwd_clk_soc_clk_hor5
place_inst soc_clk_hor5_fwd_clk_soc_clk_hor5 5555.34 948.464 R0
set_db inst:soc_clk_hor5_fwd_clk_soc_clk_hor5 .place_status fixed
connect soc_clk_hor5_fwd_clk_soc_clk_hor5/A -net soc_clk_main_mirror_L4_inv1_Y
connect soc_clk_hor5_fwd_clk_soc_clk_hor5/Y -net soc_clk_hor5_fwd_clk_soc_clk_hor5_Y

set_db timing_enable_simultaneous_setup_hold_mode true
