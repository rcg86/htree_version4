#read_tech -file ../tech.new.lef
read_tech -file ../ln04lpp_tech_18M_3Mx_2Fx_7Dx_2Hx_2Gx_2Iz_LB_3MIM.big.die.lef -min_layer D12 -max_layer IB
read_lef -file ../ln04lpp_sc_s7p94t_cdk12m3mx2fx7dx_slvt_c60l04.lef 
read_spine_spec -file ./custom_spine.yaml
read_def -file cf999.def
# Tracks are 0.72 apart; rule1 wires are 0.72 wide with 0.72 spacing, so the
# power (shield) tracks sit 2 tracks (1.44) from each signal track, NA between.
assign_track_for_route -layer IA -net {VDD_SOC NA - NA VSS NA - NA}
assign_track_for_route -layer IB -net {VDD_SOC NA - NA VSS NA - NA}
create_route_rule -name rule1 -layer {IA IB} -width 0.72 -spacing 0.72

read_pin_spec -file pin_routing_spec.yaml 



if {0} {
connect_pin -from [get_db ports {acp_clk_iose_ctm0_clk_out_31_0_clock}] -to [get_db ports {acp_clk_ctm0_app_local_clk_31}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {bisr_chip_resetn_ft_1_of_5_chip_rstn}] -to [get_db ports {bisr_chip_resetn_ft_4_of_5_chip_rstn}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {bk_pwr_rst_ft_1_of_3_bk_pwr_reset}] -to [get_db ports {bk_pwr_rst_ft_3_of_3_bk_pwr_reset}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {chip_signals_ft_1_of_3_chiplet_index[0]}] -to [get_db ports {chip_signals_ft_3_of_3_chiplet_index[0]}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {chip_signals_ft_1_of_3_chiplet_index[1]}] -to [get_db ports {chip_signals_ft_3_of_3_chiplet_index[1]}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {chip_signals_ft_1_of_3_chiplet_index[2]}] -to [get_db ports {chip_signals_ft_3_of_3_chiplet_index[2]}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {chip_signals_ft_1_of_3_chiplet_index[3]}] -to [get_db ports {chip_signals_ft_3_of_3_chiplet_index[3]}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {chip_signals_ft_1_of_3_chiplet_index[4]}] -to [get_db ports {chip_signals_ft_3_of_3_chiplet_index[4]}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {chip_signals_ft_1_of_3_primary_chiplet}] -to [get_db ports {chip_signals_ft_3_of_3_primary_chiplet}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {chip_signals_ft_1_of_3_primary_package}] -to [get_db ports {chip_signals_ft_3_of_3_primary_package}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {enet_clk_ione_ctm1_clk_out_31_1_clock}] -to [get_db ports {enet_clk_ctm1_tlp_local_clk_31}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {func_efuseSerialShiftInterface_wrap_2k_func_efuse_intf_ft_1_of_3_grp_clk}] -to [get_db ports {func_efuseSerialShiftInterface_wrap_2k_func_efuse_intf_ft_3_of_3_grp_clk}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {func_efuseSerialShiftInterface_wrap_2k_func_efuse_intf_ft_1_of_3_grp_func_efuse_update}] -to [get_db ports {func_efuseSerialShiftInterface_wrap_2k_func_efuse_intf_ft_3_of_3_grp_func_efuse_update}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {func_efuseSerialShiftInterface_wrap_2k_func_efuse_intf_ft_1_of_3_grp_resetn}] -to [get_db ports {func_efuseSerialShiftInterface_wrap_2k_func_efuse_intf_ft_3_of_3_grp_resetn}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {func_efuseSerialShiftInterface_wrap_2k_func_efuse_intf_ft_1_of_3_grp_si}] -to [get_db ports {func_efuseSerialShiftInterface_wrap_2k_func_efuse_intf_ft_3_of_3_grp_si}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {func_efuseSerialShiftInterface_wrap_2k_func_efuse_intf_ft_3_of_3_grp_so}] -to [get_db ports {func_efuseSerialShiftInterface_wrap_2k_func_efuse_intf_ft_1_of_3_grp_so}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {i2s_pll_FEED_OUT_ft_2_of_5_clock}] -to [get_db ports {i2s_pll_FEED_OUT_ft_5_of_5_clock}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {iose_pll_output_ft_1_of_3_clock}] -to [get_db ports {iose_pll_output_ft_3_of_3_clock}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {ldu0_pll_output_ft_2_of_5_clock}] -to [get_db ports {ldu0_pll_output_ft_5_of_5_clock}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {ldu1_pll_output_ft_2_of_4_clock}] -to [get_db ports {ldu1_pll_output_ft_4_of_4_clock}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {mgt_clk_ione_ctm2_clk_out_31_2_clock}] -to [get_db ports {mgt_clk_ctm2_app_local_clk_31 mgt_clk_ctm2_llq3_local_clk_21 mgt_clk_ctm2_gpp_local_clk_27 mgt_clk_ctm2_txp1_local_clk_16 mgt_clk_ctm2_eyp1_local_clk_28 mgt_clk_ctm2_tlp_clk_out_31_clock mgt_clk_ctm2_llp0_local_clk_24 mgt_clk_ctm2_dmu_local_clk_30 mgt_clk_ctm2_llq1_local_clk_22 mgt_clk_ctm2_eyp0_local_clk_29 mgt_clk_ctm2_scp_local_clk_20 mgt_clk_ctm2_ione_local_clk_26 mgt_clk_ctm2_iose_local_clk_25 mgt_clk_ctm2_llp2_local_clk_23 mgt_clk_ctm2_tlp_local_clk_19 mgt_clk_ctm2_tlq_local_clk_18 mgt_clk_ctm2_txp0_local_clk_17 mgt_clk_ctm2_upa_local_clk_15 mgt_clk_ctm2_upb_local_clk_14 mgt_clk_ctm2_eyp0_clk_out_30_clock mgt_clk_ctm2_scp_clk_out_29_clock}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {pwr_goodldu0_ft_1_of_5_pwr_good}] -to [get_db ports {pwr_goodldu0_ft_4_of_5_pwr_good}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {pwr_goodldu1_ft_1_of_3_pwr_good}] -to [get_db ports {pwr_goodldu1_ft_2_of_3_pwr_good}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {pwr_goodtlp_ft_1_of_2_pwr_good}] -to [get_db ports {pwr_goodtlp_ft_2_of_2_pwr_good}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {pwr_goodtlq_ft_1_of_3_pwr_good}] -to [get_db ports {pwr_goodtlq_ft_3_of_3_pwr_good}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {pwr_goodupa_ft_1_of_2_pwr_good}] -to [get_db ports {pwr_goodupa_ft_2_of_2_pwr_good}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {pwr_goodupb_ft_1_of_2_pwr_good}] -to [get_db ports {pwr_goodupb_ft_2_of_2_pwr_good}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {ref_clk_ione_ctm3_clk_out_31_3_clock}] -to [get_db ports {ref_clk_ctm3_eyp0_clk_out_30_clock ref_clk_ctm3_iose_local_clk_29 ref_clk_ctm3_ione_local_clk_30 ref_clk_ctm3_gpp_local_clk_31 ref_clk_ctm3_scp_local_clk_28 ref_clk_ctm3_scp_clk_out_29_clock ref_clk_ctm3_tlp_clk_out_31_clock}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {scp_chip_resetn_ft_1_of_3_chip_rstn}] -to [get_db ports {scp_chip_resetn_ft_3_of_3_chip_rstn}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {soc_clk_ione_ctm4_clk_out_31_4_clock}] -to [get_db ports {soc_clk_ctm4_app_local_clk_31 soc_clk_ctm4_iose_local_clk_25 soc_clk_ctm4_eyp0_local_clk_29 soc_clk_ctm4_llq1_local_clk_22 soc_clk_ctm4_eyp1_local_clk_28 soc_clk_ctm4_llq3_local_clk_21 soc_clk_ctm4_llp2_local_clk_23 soc_clk_ctm4_dmu_local_clk_30 soc_clk_ctm4_ione_local_clk_26 soc_clk_ctm4_gpp_local_clk_27 soc_clk_ctm4_llp0_local_clk_24 soc_clk_ctm4_scp_local_clk_20 soc_clk_ctm4_tlp_local_clk_19 soc_clk_ctm4_tlq_local_clk_18 soc_clk_ctm4_txp0_local_clk_17 soc_clk_ctm4_txp1_local_clk_16 soc_clk_ctm4_upa_local_clk_15 soc_clk_ctm4_upb_local_clk_14 soc_clk_ctm4_eyp0_clk_out_30_clock soc_clk_ctm4_scp_clk_out_29_clock soc_clk_ctm4_tlp_clk_out_31_clock}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {tlm_enet_clk_iose_ctm5_clk_out_31_5_clock}] -to [get_db ports {tlm_enet_clk_ctm5_tlq_local_clk_31}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {txe_clk_iose_ctm6_clk_out_31_6_clock}] -to [get_db ports {txe_clk_ctm6_txp0_local_clk_31 txe_clk_ctm6_txp1_local_clk_30}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {usb_aud_clk0_ione_ctm7_clk_out_31_7_clock}] -to [get_db ports {usb_aud_clk0_ctm7_gpp_local_clk_31}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
connect_pin -from [get_db ports {usb_aud_clk1_ione_ctm8_clk_out_31_8_clock}] -to [get_db ports {usb_aud_clk1_ctm8_gpp_local_clk_31}] -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04
}

create_spine -name mgt_clk_main -spec_name custom_spine_4000 -location {5697 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-x} -mirror
move_spine_to_boundary -spine mgt_clk_main -clearance {0 0 0 10} -moves {head bottom down 2075.14 left 87.84 down 3381.12 up 1008 down 201.6 up 201.6 down 103.68}


set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts mgt_clk_main*]


route_pin -inst [get_db [get_db insts mgt_clk_main*] .name] -spec_name vertical_routing
route_net -net [get_db [get_db nets mgt_clk_main*] .name] -rule rule1 -shield

route_track -compact -net [get_db [get_db nets mgt_clk_main*] .name ] -rule rule1 -shield -shield_nets {VDD_SOC VSS}
route_final_stub -stub [get_db [get_db stub mgt_clk_main*] .name] -rule rule1 -shield




create_spine -name mgt_clk_clk_spine_bot -spec_name custom_spine_v5p2 -location {5681 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-x} -mirror
move_spine_to_boundary -spine mgt_clk_clk_spine_bot -clearance {0 0 0 18} -moves {head bottom down 4064.38 left 92 down 3035.52}
#move_spine_to_boundary -spine mgt_clk_clk_spine_bot -clearance {0 0 0 18} -moves {head bottom down 4064.38 left 97.76 down 3035.52}

set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts mgt_clk_spine*]
move_obj [get_db spine mgt_clk_clk_spine_bot] -direction +y -distance 10 -legal


route_pin -inst [get_db [get_db insts mgt_clk_clk_spine_bot*] .name] -spec_name vertical_routing
route_net -net [get_db [get_db nets mgt_clk_clk_spine_bot*] .name] -rule rule1 -shield

route_track -compact -net [get_db [get_db nets mgt_clk_clk_spine_bot*] .name ] -rule rule1 -shield -shield_nets {VDD_SOC VSS}
route_final_stub -stub [get_db [get_db stub mgt_clk_clk_spine_bot*] .name] -rule rule1 -shield



create_spine -name mgt_clk_clk_spine_top -spec_name custom_spine_v5p2 -location {5681 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-x} -mirror
move_spine_to_boundary -spine mgt_clk_clk_spine_top -clearance {0 0 0 18} -moves {head top up 195.06}
move_spine_to_boundary -spine mgt_clk_clk_spine_top -clearance {0 0 0 18} -moves {head top up 783.36}


set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts mgt_clk_clk_spine_top*]


route_pin -inst [get_db [get_db insts mgt_clk_clk_spine_top*] .name] -spec_name vertical_routing
route_net -net [get_db [get_db nets mgt_clk_clk_spine_top*] .name] -rule rule1 -shield

route_track -compact -net [get_db [get_db nets mgt_clk_clk_spine_top*] .name ] -rule rule1 -shield -shield_nets {VDD_SOC VSS}
route_final_stub -stub [get_db [get_db stub mgt_clk_clk_spine_top*] .name] -rule rule1 -shield



copy_obj -from [get_db spine mgt_clk_main] -name soc_clk_main -x_shift -35 -y_shift 0
move_obj [get_db spine soc_clk_main ] -direction +y -distance 35 -legal

copy_obj -from [get_db spine mgt_clk_clk_spine_bot] -name soc_clk_bot -x_shift -35 -y_shift 0
move_obj [get_db spine soc_clk_bot] -direction +y -distance 35 -legal

copy_obj -from [get_db spine mgt_clk_clk_spine_top ] -name soc_clk_top -x_shift -35 -y_shift 0
move_obj [get_db spine soc_clk_top ] -direction +y -distance 35 -legal

set_db [get_db insts] .status fixed
set_db [get_db nets] .route_status fixed
### spine 1 horizontal (y = 10095)
create_spine -name mgt_clk_hor1 -spec_name custom_spine_h5p2 -location {3050 10079}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {+y} -mirror
create_spine -name soc_clk_hor1 -spec_name custom_spine_h5p2 -location {3050 10057}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-y} -mirror

### spine 2 horizontal (y = 8782)
create_spine -name mgt_clk_hor2 -spec_name custom_spine_h5p2 -location {3050 8760}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {+y} -mirror
create_spine -name soc_clk_hor2 -spec_name custom_spine_h5p2 -location {3050 8750}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-y} -mirror

### spine 3 horizontal (y = 6238)
create_spine -name mgt_clk_hor3 -spec_name custom_spine_h5p2 -location {3050 6216}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {+y} -mirror
create_spine -name soc_clk_hor3 -spec_name custom_spine_h5p2 -location {3050 6206}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-y} -mirror

### spine 4 horizontal (y = 3461)
create_spine -name mgt_clk_hor4 -spec_name custom_spine_h5p2 -location {3050 3439}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {+y} -mirror
create_spine -name soc_clk_hor4 -spec_name custom_spine_h5p2 -location {3050 3429}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-y} -mirror

### spine 5 horizontal (y = 916)
create_spine -name mgt_clk_hor5 -spec_name custom_spine_h5p2 -location {3050 894}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {+y} -mirror
create_spine -name soc_clk_hor5 -spec_name custom_spine_h5p2 -location {3050 884}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-y} -mirror




set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts *clk_hor*]


route_pin -inst [get_db [get_db insts *clk_hor*] .name] -spec_name horizontal_routing
route_net -net [get_db [get_db nets *clk_hor*] .name] -rule rule1 -shield

route_track -compact -net [get_db [get_db nets *clk_hor*] .name ] -rule rule1 -shield -shield_nets {VDD_SOC VSS}
route_final_stub -stub [get_db [get_db stub *clk_hor*] .name] -rule rule1 -shield



insert_vias -bottom_layer H2 -top_layer IA
assign_via_for_route


#create_spine -name mgt_clk_hor1 -spec_name custom_spine_h5p6 -location {2897 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-y} -mirror
#create_spine -name soc_clk -spec_name custom_spine_4000 -location {5697 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-x} -mirror
# cells onto the legal sites of their LEF SITE (DEF rows), before the pin routes
#move_spine_to_boundary -spine mgt_clk_clk_spine -clearance {0 0 0 10} -moves {head bottom down 57.6}

set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts]

connect_pin -from [get_db ports mgt_clk_ione_ctm2_clk_out_31_2_clock] -to [get_db [get_db spine mgt_clk_main] .spine_input] -disconnect
route_net -net [get_db net:mgt_clk_ione_ctm2_clk_out_31_2_clock] -rule rule1 -shield -shield_nets {VDD_SOC, VSS}
add_buffer_on_net -net mgt_clk_ione_ctm2_clk_out_31_2_clock -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -first_distance 100 -distance 1000 -spec_name vertical_routing

connect_pin -from [get_db ports soc_clk_ione_ctm4_clk_out_31_4_clock] -to [get_db [get_db spine soc_clk_main] .spine_input] -disconnect
route_net -net [get_db net:soc_clk_ione_ctm4_clk_out_31_4_clock ] -rule rule1 -shield -shield_nets {VDD_SOC, VSS}
add_buffer_on_net -net soc_clk_ione_ctm4_clk_out_31_4_clock -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -first_distance 100 -distance 1000 -spec_name vertical_routing

#connect_spine -from [get_db spine mgt_clk_main] -to [get_db spine mgt_clk_clk_spine_bot] -distance 2600  -buffer_distance 50 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_bot
#connect_spine -from [get_db [get_db stubs] -if {.net.name == mgt_clk_main_mirror_L4_inv1_Y}] -to [get_db spine mgt_clk_clk_spine_bot] -distance 2600  -buffer_distance 50 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_bot
set mgt_clk_spine_fwd_clk_inst [connect_spine -from [get_db [get_db stubs] -if {.net.name == mgt_clk_main_mirror_L4_inv1_Y}] -to [get_db spine mgt_clk_clk_spine_bot] -source_spine_stub_distance 5 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_bot]

set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5

legalize_placement -inst [get_db insts]

route_pin -inst [lindex $mgt_clk_spine_fwd_clk_inst 0] -spec_name vertical_routing
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -min_routing_distance 2600 -max_routing_distance 2650
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == in}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -force

add_buffer_on_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -buffer_count 1 -spread -name mid_buffer -spec_name vertical_routing

set mgt_clk_spine_fwd_clk_inst [connect_spine -from [get_db spine mgt_clk_main] -to [get_db spine mgt_clk_clk_spine_top] -source_spine_stub_distance 5 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_top]

set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5

legalize_placement -inst [get_db insts]

route_pin -inst [lindex $mgt_clk_spine_fwd_clk_inst 0] -spec_name vertical_routing
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -min_routing_distance 2600 -max_routing_distance 2650
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == in}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -force

add_buffer_on_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -buffer_count 1 -spread -name mid_buffer -spec_name vertical_routing



############################ soc clk spine connections

set mgt_clk_spine_fwd_clk_inst [connect_spine -from [get_db [get_db stubs] -if {.net.name == soc_clk_main_mirror_L4_inv1_Y}] -to [get_db spine soc_clk_bot] -source_spine_stub_distance 5 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_bot]

set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5

legalize_placement -inst [get_db insts]

route_pin -inst [lindex $mgt_clk_spine_fwd_clk_inst 0] -spec_name vertical_routing
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -min_routing_distance 2600 -max_routing_distance 2650
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == in}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -force

add_buffer_on_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -buffer_count 1 -spread -name mid_buffer -spec_name vertical_routing


set mgt_clk_spine_fwd_clk_inst [connect_spine -from [get_db spine soc_clk_main] -to [get_db spine soc_clk_top] -source_spine_stub_distance 5 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_top]

set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5

legalize_placement -inst [get_db insts]

route_pin -inst [lindex $mgt_clk_spine_fwd_clk_inst 0] -spec_name vertical_routing
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -min_routing_distance 2600 -max_routing_distance 2650
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == in}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS}  -force

add_buffer_on_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -buffer_count 1 -spread -name mid_buffer -spec_name vertical_routing
############################ mgt clk connect hori01


proc connect_spine_full {from to name} {
set mgt_clk_spine_fwd_clk_inst [connect_spine -from [get_db spine $from] -to [get_db spine $to] -source_spine_stub_distance 5 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name $name]
set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts]
route_pin -inst [lindex $mgt_clk_spine_fwd_clk_inst 0] -spec_name horizontal_routing
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -min_routing_distance 2600 -max_routing_distance 2650
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == in}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -force
add_buffer_on_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -buffer_count 1 -spread -name mid_buffer -spec_name horizontal_routing
}

connect_spine_full mgt_clk_main mgt_clk_hor1 mgt_clk_hor1_fwd_clk
connect_spine_full mgt_clk_main mgt_clk_hor2 mgt_clk_hor2_fwd_clk
connect_spine_full mgt_clk_main mgt_clk_hor3 mgt_clk_hor3_fwd_clk
connect_spine_full mgt_clk_main mgt_clk_hor4 mgt_clk_hor4_fwd_clk
connect_spine_full mgt_clk_main mgt_clk_hor5 mgt_clk_hor5_fwd_clk


connect_spine_full soc_clk_main soc_clk_hor1 soc_clk_hor1_fwd_clk
connect_spine_full soc_clk_main soc_clk_hor2 soc_clk_hor2_fwd_clk
connect_spine_full soc_clk_main soc_clk_hor3 soc_clk_hor3_fwd_clk
connect_spine_full soc_clk_main soc_clk_hor4 soc_clk_hor4_fwd_clk
connect_spine_full soc_clk_main soc_clk_hor5 soc_clk_hor5_fwd_clk




#route_pin -inst [get_db insts .name] -spec pin_routing_spec.yaml
#route_net -net [get_db nets .name] -rule rule1 -shield
#
#route_final_stub -stub [get_db stub .name] -rule rule1 -shield
#route_track -compact -net [get_db nets ] -rule rule1 -shield -shield_nets {VDD_SOC VSS}

insert_vias -bottom_layer H2 -top_layer IA
assign_via_for_route

set_db [get_db insts] .status fixed
set_db [get_db nets] .route_status fixed

write_def -output spine1.def -overwrite
write_logical -overwrite -output spine1.tcl 


