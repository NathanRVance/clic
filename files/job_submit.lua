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
		local reqCpus = job_desc.pn_min_cpus
		if reqCpus > 1000 then
			reqCpus = 0
		end
		local reqMem = job_desc.pn_min_memory
		if reqMem > 1000000 then
			reqMem = 0
		end
		local reqDisk = job_desc.pn_min_tmp_disk
		if reqDisk > 1000000 then
			reqDisk = 0
		end
		slurm.log_user("cpus: %s, mem: %s, disk: %s\n", reqCpus, reqMem, reqDisk)
		for part,attr in pairs(parts) do
			if attr.cpus >= reqCpus and attr.mem >= reqMem and attr.disk >= reqDisk then
				if bestPart == nil then
					bestPart = part
					bestAttr = attr
				else
					for index,attribute in pairs({'cpus', 'mem', 'disk'}) do
						if attr[attribute] < bestAttr[attribute] then
							bestPart = part
							bestAttr = attr
							break
						elseif attr[attribute] > bestAttr[attribute] then
							break
						end
						-- If they're equal, move to the next attribute
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
