# htree4 logical changes: Innovus script, source it to reproduce them.

# ============================================================
# Step 1: Create all nets
# ============================================================

# spine temp: root net net must exist in the design
create_net -name temp_L1_inv1_Y
create_net -name temp_L2_inv1_Y
create_net -name temp_L3_inv1_Y
create_net -name temp_L4_inv1_Y
create_net -name temp_L4_inv2_Y
create_net -name temp_L5_inv1_Y
create_net -name temp_L5_inv2_Y
create_net -name temp_L5_inv3_Y
create_net -name temp_L6_inv1_Y
create_net -name temp_L6_inv2_Y
create_net -name temp_L6_inv3_Y
create_net -name temp_L7_inv1_Y
create_net -name temp_L7_inv2_Y
create_net -name temp_L7_inv3_Y
create_net -name temp_L7_inv4_Y
create_net -name temp_L7_inv5_Y
create_net -name temp_L7_inv6_Y
create_net -name temp_mirror_L1_inv1_Y
create_net -name temp_mirror_L2_inv1_Y
create_net -name temp_mirror_L3_inv1_Y
create_net -name temp_mirror_L4_inv1_Y
create_net -name temp_mirror_L4_inv2_Y
create_net -name temp_mirror_L5_inv1_Y
create_net -name temp_mirror_L5_inv2_Y
create_net -name temp_mirror_L5_inv3_Y
create_net -name temp_mirror_L6_inv1_Y
create_net -name temp_mirror_L6_inv2_Y
create_net -name temp_mirror_L6_inv3_Y
create_net -name temp_mirror_L7_inv1_Y
create_net -name temp_mirror_L7_inv2_Y
create_net -name temp_mirror_L7_inv3_Y
create_net -name temp_mirror_L7_inv4_Y
create_net -name temp_mirror_L7_inv5_Y
create_net -name temp_mirror_L7_inv6_Y

# ============================================================
# Step 2: Place and connect spine temp level L1
# ============================================================

# temp_L1_inv1  lower-left (5695.44, 7453.912) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L1_inv1
place_inst temp_L1_inv1 5695.44 7453.912 R0
connect temp_L1_inv1/A -net net
connect temp_L1_inv1/Y -net temp_L1_inv1_Y

# temp_mirror_L1_inv1  lower-left (5695.44, 7433.846) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L1_inv1
place_inst temp_mirror_L1_inv1 5695.44 7433.846 MX
connect temp_mirror_L1_inv1/A -net net
connect temp_mirror_L1_inv1/Y -net temp_mirror_L1_inv1_Y

# ============================================================
# Step 3: Place and connect spine temp level L2
# ============================================================

# temp_L2_inv1  lower-left (5692.56, 8480.58) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L2_inv1
place_inst temp_L2_inv1 5692.56 8480.58 R0
connect temp_L2_inv1/A -net temp_L1_inv1_Y
connect temp_L2_inv1/Y -net temp_L2_inv1_Y

# temp_mirror_L2_inv1  lower-left (5692.56, 6406.67) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L2_inv1
place_inst temp_mirror_L2_inv1 5692.56 6406.67 MX
connect temp_mirror_L2_inv1/A -net temp_mirror_L1_inv1_Y
connect temp_mirror_L2_inv1/Y -net temp_mirror_L2_inv1_Y

# ============================================================
# Step 4: Place and connect spine temp level L3
# ============================================================

# temp_L3_inv1  lower-left (5689.68, 9505.216) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L3_inv1
place_inst temp_L3_inv1 5689.68 9505.216 R0
connect temp_L3_inv1/A -net temp_L2_inv1_Y
connect temp_L3_inv1/Y -net temp_L3_inv1_Y

# temp_mirror_L3_inv1  lower-left (5689.68, 5382.034) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L3_inv1
place_inst temp_mirror_L3_inv1 5689.68 5382.034 MX
connect temp_mirror_L3_inv1/A -net temp_mirror_L2_inv1_Y
connect temp_mirror_L3_inv1/Y -net temp_mirror_L3_inv1_Y

# ============================================================
# Step 5: Place and connect spine temp level L4
# ============================================================

# temp_L4_inv1  lower-left (5686.8, 9512.328) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L4_inv1
place_inst temp_L4_inv1 5686.8 9512.328 R0
connect temp_L4_inv1/A -net temp_L3_inv1_Y
connect temp_L4_inv1/Y -net temp_L4_inv1_Y

# temp_L4_inv2  lower-left (5686.8, 10532.392) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L4_inv2
place_inst temp_L4_inv2 5686.8 10532.392 R0
connect temp_L4_inv2/A -net temp_L3_inv1_Y
connect temp_L4_inv2/Y -net temp_L4_inv2_Y

# temp_mirror_L4_inv1  lower-left (5686.8, 5374.922) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L4_inv1
place_inst temp_mirror_L4_inv1 5686.8 5374.922 MX
connect temp_mirror_L4_inv1/A -net temp_mirror_L3_inv1_Y
connect temp_mirror_L4_inv1/Y -net temp_mirror_L4_inv1_Y

# temp_mirror_L4_inv2  lower-left (5686.8, 4354.858) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L4_inv2
place_inst temp_mirror_L4_inv2 5686.8 4354.858 MX
connect temp_mirror_L4_inv2/A -net temp_mirror_L3_inv1_Y
connect temp_mirror_L4_inv2/Y -net temp_mirror_L4_inv2_Y

# ============================================================
# Step 6: Place and connect spine temp level L5
# ============================================================

# temp_L5_inv1  lower-left (5683.92, 8492.772) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L5_inv1
place_inst temp_L5_inv1 5683.92 8492.772 R0
connect temp_L5_inv1/A -net temp_L4_inv1_Y
connect temp_L5_inv1/Y -net temp_L5_inv1_Y

# temp_L5_inv2  lower-left (5683.92, 10539.504) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L5_inv2
place_inst temp_L5_inv2 5683.92 10539.504 R0
connect temp_L5_inv2/A -net temp_L4_inv2_Y
connect temp_L5_inv2/Y -net temp_L5_inv2_Y

# temp_L5_inv3  lower-left (5683.92, 11562.108) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L5_inv3
place_inst temp_L5_inv3 5683.92 11562.108 R0
connect temp_L5_inv3/A -net temp_L4_inv2_Y
connect temp_L5_inv3/Y -net temp_L5_inv3_Y

# temp_mirror_L5_inv1  lower-left (5683.92, 6394.478) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L5_inv1
place_inst temp_mirror_L5_inv1 5683.92 6394.478 MX
connect temp_mirror_L5_inv1/A -net temp_mirror_L4_inv1_Y
connect temp_mirror_L5_inv1/Y -net temp_mirror_L5_inv1_Y

# temp_mirror_L5_inv2  lower-left (5683.92, 4347.746) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L5_inv2
place_inst temp_mirror_L5_inv2 5683.92 4347.746 MX
connect temp_mirror_L5_inv2/A -net temp_mirror_L4_inv2_Y
connect temp_mirror_L5_inv2/Y -net temp_mirror_L5_inv2_Y

# temp_mirror_L5_inv3  lower-left (5609.82, 3382.038) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L5_inv3
place_inst temp_mirror_L5_inv3 5609.82 3382.038 MX
connect temp_mirror_L5_inv3/A -net temp_mirror_L4_inv2_Y
connect temp_mirror_L5_inv3/Y -net temp_mirror_L5_inv3_Y

# ============================================================
# Step 7: Place and connect spine temp level L6
# ============================================================

# temp_L6_inv1  lower-left (5681.04, 8118.884) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L6_inv1
place_inst temp_L6_inv1 5681.04 8118.884 R0
connect temp_L6_inv1/A -net temp_L5_inv1_Y
connect temp_L6_inv1/Y -net temp_L6_inv1_Y

# temp_L6_inv2  lower-left (5681.04, 10163.076) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L6_inv2
place_inst temp_L6_inv2 5681.04 10163.076 R0
connect temp_L6_inv2/A -net temp_L5_inv2_Y
connect temp_L6_inv2/Y -net temp_L6_inv2_Y

# temp_L6_inv3  lower-left (5681.04, 11946.156) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L6_inv3
place_inst temp_L6_inv3 5681.04 11946.156 R0
connect temp_L6_inv3/A -net temp_L5_inv3_Y
connect temp_L6_inv3/Y -net temp_L6_inv3_Y

# temp_mirror_L6_inv1  lower-left (5681.04, 6768.366) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L6_inv1
place_inst temp_mirror_L6_inv1 5681.04 6768.366 MX
connect temp_mirror_L6_inv1/A -net temp_mirror_L5_inv1_Y
connect temp_mirror_L6_inv1/Y -net temp_mirror_L6_inv1_Y

# temp_mirror_L6_inv2  lower-left (5681.04, 4724.174) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L6_inv2
place_inst temp_mirror_L6_inv2 5681.04 4724.174 MX
connect temp_mirror_L6_inv2/A -net temp_mirror_L5_inv2_Y
connect temp_mirror_L6_inv2/Y -net temp_mirror_L6_inv2_Y

# temp_mirror_L6_inv3  lower-left (5584.56, 3037.614) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L6_inv3
place_inst temp_mirror_L6_inv3 5584.56 3037.614 MX
connect temp_mirror_L6_inv3/A -net temp_mirror_L5_inv3_Y
connect temp_mirror_L6_inv3/Y -net temp_mirror_L6_inv3_Y

# ============================================================
# Step 8: Place and connect spine temp level L7
# ============================================================

# temp_L7_inv1  lower-left (5678.16, 7949.72) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L7_inv1
place_inst temp_L7_inv1 5678.16 7949.72 R0
connect temp_L7_inv1/A -net temp_L6_inv1_Y
connect temp_L7_inv1/Y -net temp_L7_inv1_Y

# temp_L7_inv2  lower-left (5678.16, 8950.988) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L7_inv2
place_inst temp_L7_inv2 5678.16 8950.988 R0
connect temp_L7_inv2/A -net temp_L6_inv1_Y
connect temp_L7_inv2/Y -net temp_L7_inv2_Y

# temp_L7_inv3  lower-left (5678.16, 9952.764) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L7_inv3
place_inst temp_L7_inv3 5678.16 9952.764 R0
connect temp_L7_inv3/A -net temp_L6_inv2_Y
connect temp_L7_inv3/Y -net temp_L7_inv3_Y

# temp_L7_inv4  lower-left (5678.16, 10954.54) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L7_inv4
place_inst temp_L7_inv4 5678.16 10954.54 R0
connect temp_L7_inv4/A -net temp_L6_inv2_Y
connect temp_L7_inv4/Y -net temp_L7_inv4_Y

# temp_L7_inv5  lower-left (5678.16, 11956.316) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L7_inv5
place_inst temp_L7_inv5 5678.16 11956.316 R0
connect temp_L7_inv5/A -net temp_L6_inv3_Y
connect temp_L7_inv5/Y -net temp_L7_inv5_Y

# temp_L7_inv6  lower-left (5678.16, 12958.092) um, N
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_L7_inv6
place_inst temp_L7_inv6 5678.16 12958.092 R0
connect temp_L7_inv6/A -net temp_L6_inv3_Y
connect temp_L7_inv6/Y -net temp_L7_inv6_Y

# temp_mirror_L7_inv1  lower-left (5678.16, 6938.038) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L7_inv1
place_inst temp_mirror_L7_inv1 5678.16 6938.038 MX
connect temp_mirror_L7_inv1/A -net temp_mirror_L6_inv1_Y
connect temp_mirror_L7_inv1/Y -net temp_mirror_L7_inv1_Y

# temp_mirror_L7_inv2  lower-left (5678.16, 5936.262) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L7_inv2
place_inst temp_mirror_L7_inv2 5678.16 5936.262 MX
connect temp_mirror_L7_inv2/A -net temp_mirror_L6_inv1_Y
connect temp_mirror_L7_inv2/Y -net temp_mirror_L7_inv2_Y

# temp_mirror_L7_inv3  lower-left (5678.16, 4934.486) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L7_inv3
place_inst temp_mirror_L7_inv3 5678.16 4934.486 MX
connect temp_mirror_L7_inv3/A -net temp_mirror_L6_inv2_Y
connect temp_mirror_L7_inv3/Y -net temp_mirror_L7_inv3_Y

# temp_mirror_L7_inv4  lower-left (5678.16, 3932.71) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L7_inv4
place_inst temp_mirror_L7_inv4 5678.16 3932.71 MX
connect temp_mirror_L7_inv4/A -net temp_mirror_L6_inv2_Y
connect temp_mirror_L7_inv4/Y -net temp_mirror_L7_inv4_Y

# temp_mirror_L7_inv5  lower-left (5581.68, 3027.454) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L7_inv5
place_inst temp_mirror_L7_inv5 5581.68 3027.454 MX
connect temp_mirror_L7_inv5/A -net temp_mirror_L6_inv3_Y
connect temp_mirror_L7_inv5/Y -net temp_mirror_L7_inv5_Y

# temp_mirror_L7_inv6  lower-left (5581.68, 2026.186) um, FS
create_inst -cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name temp_mirror_L7_inv6
place_inst temp_mirror_L7_inv6 5581.68 2026.186 MX
connect temp_mirror_L7_inv6/A -net temp_mirror_L6_inv3_Y
connect temp_mirror_L7_inv6/Y -net temp_mirror_L7_inv6_Y

