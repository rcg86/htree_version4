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
# route_pin needs instances: it runs after create_spine below
#route_pin -spec pin_routing_spec.yaml
#create_inst -ref_cell INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04 -location {5622.772 10066.7}
#create_spine -name mgt_clk -spec_name custom_spine_4000 -location {0 0} -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -validate -show





### create mgt clock main spine
#
create_spine -name mgt_clk_spine_ver_main -spec_name custom_spine_4000 -location {5697 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-x} -mirror
move_spine_to_boundary -spine mgt_clk_spine_ver_main -clearance {0 0 0 10} -moves {head bottom down 2075.14 left 87.84 down 3381.12 up 1008 down 201.6 up 201.6 down 103.68}

create_spine -name mgt_clk_spine_bot -spec_name custom_spine_v5p2 -location {5681 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-x} -mirror
move_spine_to_boundary -spine mgt_clk_spine_bot -clearance {0 0 0 18} -moves {head bottom down 4064.38 left 92 down 3035.52}
move_obj [get_db spine mgt_clk_spine_bot ] -direction +y -distance 10 -legal

create_spine -name mgt_clk_spine_top -spec_name custom_spine_v5p2 -location {5681 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-x} -mirror
move_spine_to_boundary -spine mgt_clk_spine_top -clearance {0 0 0 18} -moves {head top up 195.06}
move_spine_to_boundary -spine mgt_clk_spine_top -clearance {0 0 0 18} -moves {head top up 783.36}


set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts mgt_clk_spine*]

route_pin -inst [get_db [get_db insts mgt_clk_spine*] .name] -spec_name vertical_routing
route_net -net [get_db [get_db nets mgt_clk_spine*] .name] -rule rule1 -shield

route_track -compact -net [get_db [get_db nets mgt_clk_spine*] .name ] -rule rule1 -shield -shield_nets {VDD_SOC VSS}
route_final_stub -stub [get_db [get_db stub mgt_clk_spine*] .name] -rule rule1 -shield
insert_vias -bottom_layer D12 -top_layer H2


copy_obj -from [get_db spine mgt_clk_spine_ver_main] -name soc_clk_spine_ver_main -x_shift -35 -y_shift 0
move_obj [get_db spine soc_clk_spine_ver_main ] -direction +y -distance 35 -legal

copy_obj -from [get_db spine mgt_clk_spine_bot] -name soc_clk_bot -x_shift -35 -y_shift 0
move_obj [get_db spine soc_clk_bot] -direction +y -distance 35 -legal

copy_obj -from [get_db spine mgt_clk_spine_top ] -name soc_clk_top -x_shift -35 -y_shift 0
move_obj [get_db spine soc_clk_top ] -direction +y -distance 35 -legal


### spine 1 horizontal (y = 10095)
create_spine -name mgt_clk_hor1 -spec_name custom_spine_h5p2 -location {2700 10079}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {+y} -mirror
create_spine -name soc_clk_hor1 -spec_name custom_spine_h5p2 -location {2730 10057}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-y} -mirror



set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts *clk_hor*]


route_pin -inst [get_db [get_db insts *clk_hor*] .name] -spec_name horizontal_routing
route_net -net [get_db [get_db nets *clk_hor*] .name] -rule rule1 -shield

route_track -compact -net [get_db [get_db nets *clk_hor*] .name ] -rule rule1 -shield -shield_nets {VDD_SOC VSS}
route_final_stub -stub [get_db [get_db stub *clk_hor*] .name] -rule rule1 -shield

insert_vias -bottom_layer D12 -top_layer H2
assign_via_for_route


### spine 2 horizontal (y = 8782)

copy_obj -from [get_db spine mgt_clk_hor1] -name mgt_clk_hor2 -x_shift 0 -y_shift 0
move_obj [get_db spine mgt_clk_hor2 ] -direction -y -distance 1319 -legal

copy_obj -from [get_db spine soc_clk_hor1] -name soc_clk_hor2 -x_shift 0 -y_shift 0
move_obj [get_db spine soc_clk_hor2 ] -direction -y -distance 1307 -legal

### spine 3 horizontal (y = 6238)


copy_obj -from [get_db spine mgt_clk_hor1] -name mgt_clk_hor3 -x_shift 0 -y_shift 0
move_obj [get_db spine mgt_clk_hor3 ] -direction -y -distance 3863 -legal

copy_obj -from [get_db spine soc_clk_hor1] -name soc_clk_hor3 -x_shift 0 -y_shift 0
move_obj [get_db spine soc_clk_hor3 ] -direction -y -distance 3851 -legal

### spine 4 horizontal (y = 3461)

copy_obj -from [get_db spine mgt_clk_hor1] -name mgt_clk_hor4 -x_shift 0 -y_shift 0
move_obj [get_db spine mgt_clk_hor4 ] -direction -y -distance 6640 -legal

copy_obj -from [get_db spine soc_clk_hor1] -name soc_clk_hor4 -x_shift 0 -y_shift 0
move_obj [get_db spine soc_clk_hor4 ] -direction -y -distance 6628 -legal

### spine 5 horizontal (y = 916)


copy_obj -from [get_db spine mgt_clk_hor1] -name mgt_clk_hor5 -x_shift 0 -y_shift 0
move_obj [get_db spine mgt_clk_hor5 ] -direction -y -distance 9185 -legal

copy_obj -from [get_db spine soc_clk_hor1] -name soc_clk_hor5 -x_shift 0 -y_shift 0
move_obj [get_db spine soc_clk_hor5 ] -direction -y -distance 9173 -legal




#create_spine -name mgt_clk_hor1 -spec_name custom_spine_h5p6 -location {2897 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-y} -mirror
#create_spine -name soc_clk -spec_name custom_spine_4000 -location {5697 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-x} -mirror
# cells onto the legal sites of their LEF SITE (DEF rows), before the pin routes
#move_spine_to_boundary -spine mgt_clk_clk_spine -clearance {0 0 0 10} -moves {head bottom down 57.6}

set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts]

connect_pin -from [get_db ports mgt_clk_ione_ctm2_clk_out_31_2_clock] -to [get_db [get_db spine mgt_clk_spine_ver_main] .spine_input] -disconnect
route_net -net [get_db net:mgt_clk_ione_ctm2_clk_out_31_2_clock] -rule rule1 -shield -shield_nets {VDD_SOC, VSS}
add_buffer_on_net -net mgt_clk_ione_ctm2_clk_out_31_2_clock -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -first_distance 100 -distance 1000 -spec_name vertical_routing

connect_pin -from [get_db ports soc_clk_ione_ctm4_clk_out_31_4_clock] -to [get_db [get_db spine soc_clk_spine_ver_main] .spine_input] -disconnect
route_net -net [get_db net:soc_clk_ione_ctm4_clk_out_31_4_clock ] -rule rule1 -shield -shield_nets {VDD_SOC, VSS}
add_buffer_on_net -net soc_clk_ione_ctm4_clk_out_31_4_clock -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -first_distance 100 -distance 1000 -spec_name vertical_routing

#connect_spine -from [get_db spine mgt_clk_spine_ver_main] -to [get_db spine mgt_clk_spine_bot] -distance 2600  -buffer_distance 50 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_bot
#connect_spine -from [get_db [get_db stubs] -if {.net.name == mgt_clk_spine_ver_main_mirror_L4_inv1_Y}] -to [get_db spine mgt_clk_spine_bot] -distance 2600  -buffer_distance 50 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_bot
set mgt_clk_spine_fwd_clk_inst [connect_spine -from [get_db [get_db stubs] -if {.net.name == mgt_clk_spine_ver_main_mirror_L4_inv1_Y}] -to [get_db spine mgt_clk_spine_bot] -source_spine_stub_distance 5 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_bot]

set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5

legalize_placement -inst [get_db insts]

route_pin -inst [lindex $mgt_clk_spine_fwd_clk_inst 0] -spec_name vertical_routing
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -min_routing_distance 2600 -max_routing_distance 2650
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == in}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -force

add_buffer_on_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -buffer_count 1 -spread -name mid_buffer -spec_name vertical_routing

set mgt_clk_spine_fwd_clk_inst [connect_spine -from [get_db spine mgt_clk_spine_ver_main] -to [get_db spine mgt_clk_spine_top] -source_spine_stub_distance 5 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_top]

set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5

legalize_placement -inst [get_db insts]

route_pin -inst [lindex $mgt_clk_spine_fwd_clk_inst 0] -spec_name vertical_routing
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -min_routing_distance 2600 -max_routing_distance 2650
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == in}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -force

add_buffer_on_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -buffer_count 1 -spread -name mid_buffer -spec_name vertical_routing



############################ soc clk spine connections

set mgt_clk_spine_fwd_clk_inst [connect_spine -from [get_db [get_db stubs] -if {.net.name == soc_clk_spine_ver_main_mirror_L4_inv1_Y}] -to [get_db spine soc_clk_bot] -source_spine_stub_distance 5 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_bot]

set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5

legalize_placement -inst [get_db insts]

route_pin -inst [lindex $mgt_clk_spine_fwd_clk_inst 0] -spec_name vertical_routing
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -min_routing_distance 2600 -max_routing_distance 2650
route_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == in}] .net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -force

add_buffer_on_net -net [get_db [get_db [get_db insts [lindex $mgt_clk_spine_fwd_clk_inst 0]] .pins -if {.direction == out}] .net.name] -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -buffer_count 1 -spread -name mid_buffer -spec_name vertical_routing


set mgt_clk_spine_fwd_clk_inst [connect_spine -from [get_db spine soc_clk_spine_ver_main] -to [get_db spine soc_clk_top] -source_spine_stub_distance 5 -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name spine_connect_top]

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

connect_spine_full mgt_clk_spine_ver_main mgt_clk_hor1 mgt_clk_hor1_fwd_clk
connect_spine_full mgt_clk_spine_ver_main mgt_clk_hor2 mgt_clk_hor2_fwd_clk
connect_spine_full mgt_clk_spine_ver_main mgt_clk_hor3 mgt_clk_hor3_fwd_clk
connect_spine_full mgt_clk_spine_ver_main mgt_clk_hor4 mgt_clk_hor4_fwd_clk
connect_spine_full mgt_clk_spine_ver_main mgt_clk_hor5 mgt_clk_hor5_fwd_clk


connect_spine_full soc_clk_spine_ver_main soc_clk_hor1 soc_clk_hor1_fwd_clk
connect_spine_full soc_clk_spine_ver_main soc_clk_hor2 soc_clk_hor2_fwd_clk
connect_spine_full soc_clk_spine_ver_main soc_clk_hor3 soc_clk_hor3_fwd_clk
connect_spine_full soc_clk_spine_ver_main soc_clk_hor4 soc_clk_hor4_fwd_clk
connect_spine_full soc_clk_spine_ver_main soc_clk_hor5 soc_clk_hor5_fwd_clk

connect_pin -from ref_clk_ione_ctm3_clk_out_31_3_clock -to {ref_clk_ctm3_eyp0_clk_out_30_clock ref_clk_ctm3_iose_local_clk_29 ref_clk_ctm3_scp_local_clk_28 ref_clk_ctm3_scp_clk_out_29_clock ref_clk_ctm3_tlp_clk_out_31_clock ref_clk_ctm3_ione_local_clk_30 ref_clk_ctm3_gpp_local_clk_31} -ref_cell INV12M3Mx2Fx7Dx_D48_N_S7P94TSL_C60L04

create_buffer_tree -from ref_clk_ione_ctm3_clk_out_31_3_clock -inverter_ref INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -name buffer_tree_ref_clk -topology shortest -distance 700




#### connect the clock output
#mgt_clk_spine_bot_mirror_L3_inv1_Y
proc clk_output_conn {from port spec layer} {
set op_buf [connect_spine -from [get_db spine $from] -to [get_db ports $port] -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -source_spine_stub_distance 5 -name ${from}_ ]
route_pin -inst [get_db [get_db [lindex $op_buf 0]] .inst.name] -spec_name ${spec}_routing
route_net  -net [get_db [get_db [lindex $op_buf 0]] .inst.pins.net.name] -rule rule1 -shield -shield_nets {VDD_SOC, VSS} -force
#promote_port_to_layer -width 0.72 -port $port -layer $layer -snap_to_track
}


clk_output_conn mgt_clk_spine_bot mgt_clk_ctm2_iose_local_clk_25 vertical IB
clk_output_conn mgt_clk_spine_top mgt_clk_ctm2_upb_local_clk_14 vertical IA
clk_output_conn mgt_clk_spine_bot mgt_clk_ctm2_txp1_local_clk_16 vertical IA
clk_output_conn mgt_clk_hor4 mgt_clk_ctm2_txp0_local_clk_17 horizontal IB
clk_output_conn mgt_clk_hor1 mgt_clk_ctm2_tlp_local_clk_19 horizontal IB
clk_output_conn mgt_clk_hor1 mgt_clk_ctm2_tlp_clk_out_31_clock horizontal IA
clk_output_conn mgt_clk_hor4 mgt_clk_ctm2_scp_local_clk_20 horizontal IA
clk_output_conn mgt_clk_hor4 mgt_clk_ctm2_scp_clk_out_29_clock horizontal IA 
clk_output_conn mgt_clk_hor2 mgt_clk_ctm2_llq3_local_clk_21 horizontal IB 
clk_output_conn mgt_clk_hor5 mgt_clk_ctm2_llq1_local_clk_22 horizontal IB
clk_output_conn mgt_clk_hor2 mgt_clk_ctm2_llp2_local_clk_23 horizontal IB
clk_output_conn mgt_clk_hor1 mgt_clk_ctm2_llp0_local_clk_24 horizontal IB
clk_output_conn mgt_clk_spine_top mgt_clk_ctm2_gpp_local_clk_27 vertical IA
clk_output_conn mgt_clk_hor2 mgt_clk_ctm2_eyp1_local_clk_28 horizontal IA
clk_output_conn mgt_clk_hor1 mgt_clk_ctm2_eyp0_local_clk_29 horizontal IA
clk_output_conn mgt_clk_hor1 mgt_clk_ctm2_eyp0_clk_out_30_clock horizontal IA
clk_output_conn mgt_clk_spine_top mgt_clk_ctm2_dmu_local_clk_30 vertical IA
clk_output_conn mgt_clk_hor3 mgt_clk_ctm2_app_local_clk_31 horizontal IB



clk_output_conn soc_clk_top soc_clk_ctm4_upb_local_clk_14 vertical IA
clk_output_conn soc_clk_bot soc_clk_ctm4_upa_local_clk_15 vertical IA
clk_output_conn soc_clk_hor3 soc_clk_ctm4_txp1_local_clk_16 horizontal IB
clk_output_conn soc_clk_hor4 soc_clk_ctm4_txp0_local_clk_17 horizontal IB
clk_output_conn soc_clk_bot soc_clk_ctm4_tlq_local_clk_18 vertical IA
clk_output_conn soc_clk_hor1 soc_clk_ctm4_tlp_local_clk_19 horizontal IB
clk_output_conn soc_clk_hor1 soc_clk_ctm4_tlp_clk_out_31_clock horizontal IA
clk_output_conn soc_clk_hor4 soc_clk_ctm4_scp_local_clk_20 horizontal IA
clk_output_conn soc_clk_hor4 soc_clk_ctm4_scp_clk_out_29_clock horizontal IA
clk_output_conn soc_clk_hor2 soc_clk_ctm4_llq3_local_clk_21 horizontal IB
clk_output_conn soc_clk_hor5 soc_clk_ctm4_llq1_local_clk_22 horizontal IB
clk_output_conn soc_clk_hor2 soc_clk_ctm4_llp2_local_clk_23 horizontal IB
clk_output_conn soc_clk_hor5 soc_clk_ctm4_llp0_local_clk_24 horizontal IB
clk_output_conn soc_clk_top soc_clk_ctm4_ione_local_clk_26 vertical IA
clk_output_conn soc_clk_top soc_clk_ctm4_gpp_local_clk_27 vertical IA
clk_output_conn soc_clk_hor2 soc_clk_ctm4_eyp1_local_clk_28 horizontal IA
clk_output_conn soc_clk_hor5 soc_clk_ctm4_eyp0_local_clk_29 horizontal IA
clk_output_conn soc_clk_hor5 soc_clk_ctm4_eyp0_clk_out_30_clock horizontal IA
clk_output_conn soc_clk_top soc_clk_ctm4_dmu_local_clk_30 vertical IA
clk_output_conn soc_clk_hor3 soc_clk_ctm4_app_local_clk_31 horizontal IA
clk_output_conn soc_clk_bot soc_clk_ctm4_iose_local_clk_25 vertical IB


#route_pin -inst [get_db insts .name] -spec pin_routing_spec.yaml
#route_net -net [get_db nets .name] -rule rule1 -shield
#
#route_final_stub -stub [get_db stub .name] -rule rule1 -shield
#route_track -compact -net [get_db nets ] -rule rule1 -shield -shield_nets {VDD_SOC VSS}

insert_vias -bottom_layer H2 -top_layer IA
assign_via_for_route

set_db [get_db insts] .status fixed
set_db [get_db nets] .route_status fixed

insert_pg_grid -layer IA -pull_back_distance 1
insert_pg_grid -layer IB -pull_back_distance 1
optimize_pg_connection -extend 5 -inst [get_db insts]

write_def -output spine1.def -overwrite
write_logical -overwrite -output spine1.tcl 


