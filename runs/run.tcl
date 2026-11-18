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
# route_pin needs instances: it runs after create_spine below
#route_pin -spec pin_routing_spec.yaml
#create_inst -ref_cell INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04 -location {5622.772 10066.7}
#create_spine -name mgt_clk -spec_name custom_spine_4000 -location {0 0} -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -validate -show
create_spine -name mgt_clk_main -spec_name custom_spine_4000 -location {5697 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-x} -mirror
move_spine_to_boundary -spine mgt_clk_main -clearance {0 0 0 10} -moves {head bottom down 2075.14 left 87.84 down 3381.12 up 1008 down 201.6 up 201.6 down 103.68}


set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts mgt_clk_main*]


route_pin -inst [get_db [get_db insts mgt_clk_main*] .name] -spec pin_routing_spec.yaml
route_net -net [get_db [get_db nets mgt_clk_main*] .name] -rule rule1 -shield

route_track -compact -net [get_db [get_db nets mgt_clk_main*] .name ] -rule rule1 -shield -shield_nets {VDD_SOC VSS}
route_final_stub -stub [get_db [get_db stub mgt_clk_main*] .name] -rule rule1 -shield




create_spine -name mgt_clk_clk_spine_bot -spec_name custom_spine_v5p2 -location {5681 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-x} -mirror
move_spine_to_boundary -spine mgt_clk_clk_spine_bot -clearance {0 0 0 18} -moves {head bottom down 4064.38 left 92 down 3035.52}
#move_spine_to_boundary -spine mgt_clk_clk_spine_bot -clearance {0 0 0 18} -moves {head bottom down 4064.38 left 97.76 down 3035.52}

set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts mgt_clk_spine*]
move_obj [get_db spine mgt_clk_clk_spine_bot] -direction +y -distance 10 -legal


route_pin -inst [get_db [get_db insts mgt_clk_clk_spine_bot*] .name] -spec pin_routing_spec.yaml
route_net -net [get_db [get_db nets mgt_clk_clk_spine_bot*] .name] -rule rule1 -shield

route_track -compact -net [get_db [get_db nets mgt_clk_clk_spine_bot*] .name ] -rule rule1 -shield -shield_nets {VDD_SOC VSS}
route_final_stub -stub [get_db [get_db stub mgt_clk_clk_spine_bot*] .name] -rule rule1 -shield



create_spine -name mgt_clk_clk_spine_top -spec_name custom_spine_v5p2 -location {5681 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-x} -mirror
move_spine_to_boundary -spine mgt_clk_clk_spine_top -clearance {0 0 0 18} -moves {head top up 195.06}
move_spine_to_boundary -spine mgt_clk_clk_spine_top -clearance {0 0 0 18} -moves {head top up 783.36}


set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts mgt_clk_clk_spine_top*]


route_pin -inst [get_db [get_db insts mgt_clk_clk_spine_top*] .name] -spec pin_routing_spec.yaml
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

write_def -output spine1.def -overwrite
write_logical -overwrite -output spine1.tcl 

### spine 1 horizontal (y = 10095)
create_spine -name mgt_clk_hor1 -spec_name custom_spine_h5p2 -location {3050 10073}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {+y} -mirror
create_spine -name soc_clk_hor1 -spec_name custom_spine_h5p2 -location {3050 10063}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-y} -mirror

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


route_pin -inst [get_db [get_db insts *clk_hor*] .name] -spec pin_routing_spec.yaml
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

#connect_pin -from [get_db ports mgt_clk_ione_ctm2_clk_out_31_2_clock] -to [get_db [get_db spine mgt_clk] .spine_input] -disconnect
#route_net -net [get_db net:mgt_clk_ione_ctm2_clk_out_31_2_clock] -rule rule1 -shield -shield_nets {VDD_SOC, VSS}

route_pin -inst [get_db insts .name] -spec pin_routing_spec.yaml
route_net -net [get_db nets .name] -rule rule1 -shield

route_final_stub -stub [get_db stub .name] -rule rule1 -shield
route_track -compact -net [get_db nets ] -rule rule1 -shield -shield_nets {VDD_SOC VSS}

