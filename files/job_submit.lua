--[[
--	This file is edited by clic. Lines modified by clic are denoted with comments.
--	Edit at your own risk!
--]]

function slurm_job_submit(job_desc, part_list, submit_uid)
--	parts follows syntax {partName = {cpus = X, disk = Y, mem = Z}, ...}
	parts = {}
--	START CLIC STUFF
-- 	END CLIC STUFF
	if job_desc.partition == nil then
		bestPart = nil
		bestAttr = nil
		for part,attr in pairs(parts) do
			if attr.cpus >= job_desc.pn_min_cpus and attr.disk >= job_desc.pn_min_tmp_disk and attr.mem >= job_desc.pn_min_memory then
				if bestPart == nil then
					bestPart = part
					bestAttr = attr
				else
					for attribute in {'cpus', 'mem', 'disk'} do
						if attr.attribute < bestAttr.attribute then
							bestPart = part
							bestAttr = attr
							break
						elseif attr.attribute > bestAttr.attribute then
							break -- If they're equal, move to the next attribute
						end
					end
				end
			end
		end
		job_desc.partition = bestPart
	end
	return slurm.SUCCESS
end

function slurm_job_modify(job_desc, job_rec, part_list, modify_uid)
	return slurm.SUCCESS
end

slurm.log_info("initialized")
return slurm.SUCCESS
